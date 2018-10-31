#!/usr/bin/env python
"""Create a "virtual" Python installation"""

# fmt: off
import os  # isort:skip
import sys  # isort:skip

# If we are running in a new interpreter to create a virtualenv,
# we do NOT want paths from our existing location interfering with anything,
# So we remove this file's directory from sys.path - most likely to be
# the previous interpreter's site-packages. Solves #705, #763, #779
if os.environ.get("VIRTUALENV_INTERPRETER_RUNNING"):
    for path in sys.path[:]:
        if os.path.realpath(os.path.dirname(__file__)) == os.path.realpath(path):
            sys.path.remove(path)
# fmt: on

import base64
import codecs
import distutils.spawn
import distutils.sysconfig
import errno
import glob
import logging
import optparse
import os
import re
import shutil
import struct
import subprocess
import sys
import textwrap
import zlib
from distutils.util import strtobool
from os.path import join

try:
    import ConfigParser
except ImportError:
    import configparser as ConfigParser

__version__ = "16.1.0.dev0"
virtualenv_version = __version__  # legacy

if sys.version_info < (2, 7):
    print("ERROR: %s" % sys.exc_info()[1])
    print("ERROR: this script requires Python 2.7 or greater.")
    sys.exit(101)

try:
    basestring
except NameError:
    basestring = str

py_version = "python{}.{}".format(sys.version_info[0], sys.version_info[1])

is_jython = sys.platform.startswith("java")
is_pypy = hasattr(sys, "pypy_version_info")
is_win = sys.platform == "win32"
is_cygwin = sys.platform == "cygwin"
is_darwin = sys.platform == "darwin"
abiflags = getattr(sys, "abiflags", "")

user_dir = os.path.expanduser("~")
if is_win:
    default_storage_dir = os.path.join(user_dir, "virtualenv")
else:
    default_storage_dir = os.path.join(user_dir, ".virtualenv")
default_config_file = os.path.join(default_storage_dir, "virtualenv.ini")

if is_pypy:
    expected_exe = "pypy"
elif is_jython:
    expected_exe = "jython"
else:
    expected_exe = "python"

# Return a mapping of version -> Python executable
# Only provided for Windows, where the information in the registry is used
if not is_win:

    def get_installed_pythons():
        return {}


else:
    try:
        import winreg
    except ImportError:
        import _winreg as winreg

    def get_installed_pythons():
        exes = dict()
        # If both system and current user installations are found for a
        # particular Python version, the current user one is used
        for key in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
            try:
                python_core = winreg.CreateKey(key, "Software\\Python\\PythonCore")
            except WindowsError:
                # No registered Python installations
                continue
            i = 0
            while True:
                try:
                    version = winreg.EnumKey(python_core, i)
                    i += 1
                    try:
                        path = winreg.QueryValue(python_core, "%s\\InstallPath" % version)
                    except WindowsError:
                        continue
                    exes[version] = join(path, "python.exe")
                except WindowsError:
                    break
            winreg.CloseKey(python_core)

        # For versions that track separate 32-bit (`X.Y-32`) & 64-bit (`X-Y`)
        # installation registrations, add a `X.Y-64` version tag and make the
        # extensionless `X.Y` version tag represent the 64-bit installation if
        # available or 32-bit if it is not
        updated = {}
        for ver in exes:
            if ver < "3.5":
                continue
            if ver.endswith("-32"):
                base_ver = ver[:-3]
                if base_ver not in exes:
                    updated[base_ver] = exes[ver]
            else:
                updated[ver + "-64"] = exes[ver]
        exes.update(updated)

        # Add the major versions
        # Sort the keys, then repeatedly update the major version entry
        # Last executable (i.e., highest version) wins with this approach,
        # 64-bit over 32-bit if both are found
        for ver in sorted(exes):
            exes[ver[0]] = exes[ver]

        return exes


REQUIRED_MODULES = [
    "os",
    "posix",
    "posixpath",
    "nt",
    "ntpath",
    "genericpath",
    "fnmatch",
    "locale",
    "encodings",
    "codecs",
    "stat",
    "UserDict",
    "readline",
    "copy_reg",
    "types",
    "re",
    "sre",
    "sre_parse",
    "sre_constants",
    "sre_compile",
    "zlib",
]

REQUIRED_FILES = ["lib-dynload", "config"]

majver, minver = sys.version_info[:2]
if majver == 2:
    if minver >= 6:
        REQUIRED_MODULES.extend(["warnings", "linecache", "_abcoll", "abc"])
    if minver >= 7:
        REQUIRED_MODULES.extend(["_weakrefset"])
elif majver == 3:
    # Some extra modules are needed for Python 3, but different ones
    # for different versions.
    REQUIRED_MODULES.extend(
        [
            "_abcoll",
            "warnings",
            "linecache",
            "abc",
            "io",
            "_weakrefset",
            "copyreg",
            "tempfile",
            "random",
            "__future__",
            "collections",
            "keyword",
            "tarfile",
            "shutil",
            "struct",
            "copy",
            "tokenize",
            "token",
            "functools",
            "heapq",
            "bisect",
            "weakref",
            "reprlib",
        ]
    )
    if minver >= 2:
        REQUIRED_FILES[-1] = "config-%s" % majver
    if minver >= 3:
        import sysconfig

        platdir = sysconfig.get_config_var("PLATDIR")
        REQUIRED_FILES.append(platdir)
        REQUIRED_MODULES.extend(["base64", "_dummy_thread", "hashlib", "hmac", "imp", "importlib", "rlcompleter"])
    if minver >= 4:
        REQUIRED_MODULES.extend(["operator", "_collections_abc", "_bootlocale"])
    if minver >= 6:
        REQUIRED_MODULES.extend(["enum"])

if is_pypy:
    # these are needed to correctly display the exceptions that may happen
    # during the bootstrap
    REQUIRED_MODULES.extend(["traceback", "linecache"])

    if majver == 3:
        # _functools is needed to import locale during stdio initialization and
        # needs to be copied on PyPy because it's not built in
        REQUIRED_MODULES.append("_functools")


class Logger(object):

    """
    Logging object for use in command-line script.  Allows ranges of
    levels, to avoid some redundancy of displayed information.
    """

    DEBUG = logging.DEBUG
    INFO = logging.INFO
    NOTIFY = (logging.INFO + logging.WARN) / 2
    WARN = WARNING = logging.WARN
    ERROR = logging.ERROR
    FATAL = logging.FATAL

    LEVELS = [DEBUG, INFO, NOTIFY, WARN, ERROR, FATAL]

    def __init__(self, consumers):
        self.consumers = consumers
        self.indent = 0
        self.in_progress = None
        self.in_progress_hanging = False

    def debug(self, msg, *args, **kw):
        self.log(self.DEBUG, msg, *args, **kw)

    def info(self, msg, *args, **kw):
        self.log(self.INFO, msg, *args, **kw)

    def notify(self, msg, *args, **kw):
        self.log(self.NOTIFY, msg, *args, **kw)

    def warn(self, msg, *args, **kw):
        self.log(self.WARN, msg, *args, **kw)

    def error(self, msg, *args, **kw):
        self.log(self.ERROR, msg, *args, **kw)

    def fatal(self, msg, *args, **kw):
        self.log(self.FATAL, msg, *args, **kw)

    def log(self, level, msg, *args, **kw):
        if args:
            if kw:
                raise TypeError("You may give positional or keyword arguments, not both")
        args = args or kw
        rendered = None
        for consumer_level, consumer in self.consumers:
            if self.level_matches(level, consumer_level):
                if self.in_progress_hanging and consumer in (sys.stdout, sys.stderr):
                    self.in_progress_hanging = False
                    print("")
                    sys.stdout.flush()
                if rendered is None:
                    if args:
                        rendered = msg % args
                    else:
                        rendered = msg
                    rendered = " " * self.indent + rendered
                if hasattr(consumer, "write"):
                    consumer.write(rendered + "\n")
                else:
                    consumer(rendered)

    def start_progress(self, msg):
        assert not self.in_progress, "Tried to start_progress({!r}) while in_progress {!r}".format(
            msg, self.in_progress
        )
        if self.level_matches(self.NOTIFY, self._stdout_level()):
            print(msg)
            sys.stdout.flush()
            self.in_progress_hanging = True
        else:
            self.in_progress_hanging = False
        self.in_progress = msg

    def end_progress(self, msg="done."):
        assert self.in_progress, "Tried to end_progress without start_progress"
        if self.stdout_level_matches(self.NOTIFY):
            if not self.in_progress_hanging:
                # Some message has been printed out since start_progress
                print("...{}{}".format(self.in_progress, msg))
                sys.stdout.flush()
            else:
                print(msg)
                sys.stdout.flush()
        self.in_progress = None
        self.in_progress_hanging = False

    def show_progress(self):
        """If we are in a progress scope, and no log messages have been
        shown, write out another '.'"""
        if self.in_progress_hanging:
            print(".")
            sys.stdout.flush()

    def stdout_level_matches(self, level):
        """Returns true if a message at this level will go to stdout"""
        return self.level_matches(level, self._stdout_level())

    def _stdout_level(self):
        """Returns the level that stdout runs at"""
        for level, consumer in self.consumers:
            if consumer is sys.stdout:
                return level
        return self.FATAL

    def level_matches(self, level, consumer_level):
        """
        >>> l = Logger([])
        >>> l.level_matches(3, 4)
        False
        >>> l.level_matches(3, 2)
        True
        >>> l.level_matches(slice(None, 3), 3)
        False
        >>> l.level_matches(slice(None, 3), 2)
        True
        >>> l.level_matches(slice(1, 3), 1)
        True
        >>> l.level_matches(slice(2, 3), 1)
        False
        """
        if isinstance(level, slice):
            start, stop = level.start, level.stop
            if start is not None and start > consumer_level:
                return False
            if stop is not None and stop <= consumer_level:
                return False
            return True
        else:
            return level >= consumer_level

    @classmethod
    def level_for_integer(cls, level):
        levels = cls.LEVELS
        if level < 0:
            return levels[0]
        if level >= len(levels):
            return levels[-1]
        return levels[level]


# create a silent logger just to prevent this from being undefined
# will be overridden with requested verbosity main() is called.
logger = Logger([(Logger.LEVELS[-1], sys.stdout)])


def mkdir(path):
    if not os.path.exists(path):
        logger.info("Creating %s", path)
        os.makedirs(path)
    else:
        logger.info("Directory %s already exists", path)


def copyfileordir(src, dest, symlink=True):
    if os.path.isdir(src):
        shutil.copytree(src, dest, symlink)
    else:
        shutil.copy2(src, dest)


def copyfile(src, dest, symlink=True):
    if not os.path.exists(src):
        # Some bad symlink in the src
        logger.warn("Cannot find file %s (bad symlink)", src)
        return
    if os.path.exists(dest):
        logger.debug("File %s already exists", dest)
        return
    if not os.path.exists(os.path.dirname(dest)):
        logger.info("Creating parent directories for %s", os.path.dirname(dest))
        os.makedirs(os.path.dirname(dest))
    if not os.path.islink(src):
        srcpath = os.path.abspath(src)
    else:
        srcpath = os.readlink(src)
    if symlink and hasattr(os, "symlink") and not is_win:
        logger.info("Symlinking %s", dest)
        try:
            os.symlink(srcpath, dest)
        except (OSError, NotImplementedError):
            logger.info("Symlinking failed, copying to %s", dest)
            copyfileordir(src, dest, symlink)
    else:
        logger.info("Copying to %s", dest)
        copyfileordir(src, dest, symlink)


def writefile(dest, content, overwrite=True):
    if not os.path.exists(dest):
        logger.info("Writing %s", dest)
        with open(dest, "wb") as f:
            f.write(content.encode("utf-8"))
        return
    else:
        with open(dest, "rb") as f:
            c = f.read()
        if c != content.encode("utf-8"):
            if not overwrite:
                logger.notify("File %s exists with different content; not overwriting", dest)
                return
            logger.notify("Overwriting %s with new content", dest)
            with open(dest, "wb") as f:
                f.write(content.encode("utf-8"))
        else:
            logger.info("Content %s already in place", dest)


def rmtree(dir):
    if os.path.exists(dir):
        logger.notify("Deleting tree %s", dir)
        shutil.rmtree(dir)
    else:
        logger.info("Do not need to delete %s; already gone", dir)


def make_exe(fn):
    if hasattr(os, "chmod"):
        oldmode = os.stat(fn).st_mode & 0xFFF  # 0o7777
        newmode = (oldmode | 0x16D) & 0xFFF  # 0o555, 0o7777
        os.chmod(fn, newmode)
        logger.info("Changed mode of %s to %s", fn, oct(newmode))


def _find_file(filename, dirs):
    for dir in reversed(dirs):
        files = glob.glob(os.path.join(dir, filename))
        if files and os.path.isfile(files[0]):
            return True, files[0]
    return False, filename


def file_search_dirs():
    here = os.path.dirname(os.path.abspath(__file__))
    dirs = [here, join(here, "virtualenv_support")]
    if os.path.splitext(os.path.dirname(__file__))[0] != "virtualenv":
        # Probably some boot script; just in case virtualenv is installed...
        try:
            import virtualenv
        except ImportError:
            pass
        else:
            dirs.append(os.path.join(os.path.dirname(virtualenv.__file__), "virtualenv_support"))
    return [d for d in dirs if os.path.isdir(d)]


class UpdatingDefaultsHelpFormatter(optparse.IndentedHelpFormatter):
    """
    Custom help formatter for use in ConfigOptionParser that updates
    the defaults before expanding them, allowing them to show up correctly
    in the help listing
    """

    def expand_default(self, option):
        if self.parser is not None:
            self.parser.update_defaults(self.parser.defaults)
        return optparse.IndentedHelpFormatter.expand_default(self, option)


class ConfigOptionParser(optparse.OptionParser):
    """
    Custom option parser which updates its defaults by checking the
    configuration files and environmental variables
    """

    def __init__(self, *args, **kwargs):
        self.config = ConfigParser.RawConfigParser()
        self.files = self.get_config_files()
        self.config.read(self.files)
        optparse.OptionParser.__init__(self, *args, **kwargs)

    def get_config_files(self):
        config_file = os.environ.get("VIRTUALENV_CONFIG_FILE", False)
        if config_file and os.path.exists(config_file):
            return [config_file]
        return [default_config_file]

    def update_defaults(self, defaults):
        """
        Updates the given defaults with values from the config files and
        the environ. Does a little special handling for certain types of
        options (lists).
        """
        # Then go and look for the other sources of configuration:
        config = {}
        # 1. config files
        config.update(dict(self.get_config_section("virtualenv")))
        # 2. environmental variables
        config.update(dict(self.get_environ_vars()))
        # Then set the options with those values
        for key, val in config.items():
            key = key.replace("_", "-")
            if not key.startswith("--"):
                key = "--%s" % key  # only prefer long opts
            option = self.get_option(key)
            if option is not None:
                # ignore empty values
                if not val:
                    continue
                # handle multiline configs
                if option.action == "append":
                    val = val.split()
                else:
                    option.nargs = 1
                if option.action == "store_false":
                    val = not strtobool(val)
                elif option.action in ("store_true", "count"):
                    val = strtobool(val)
                try:
                    val = option.convert_value(key, val)
                except optparse.OptionValueError:
                    e = sys.exc_info()[1]
                    print("An error occurred during configuration: %s" % e)
                    sys.exit(3)
                defaults[option.dest] = val
        return defaults

    def get_config_section(self, name):
        """
        Get a section of a configuration
        """
        if self.config.has_section(name):
            return self.config.items(name)
        return []

    def get_environ_vars(self, prefix="VIRTUALENV_"):
        """
        Returns a generator with all environmental vars with prefix VIRTUALENV
        """
        for key, val in os.environ.items():
            if key.startswith(prefix):
                yield (key.replace(prefix, "").lower(), val)

    def get_default_values(self):
        """
        Overridding to make updating the defaults after instantiation of
        the option parser possible, update_defaults() does the dirty work.
        """
        if not self.process_default_values:
            # Old, pre-Optik 1.5 behaviour.
            return optparse.Values(self.defaults)

        defaults = self.update_defaults(self.defaults.copy())  # ours
        for option in self._get_all_options():
            default = defaults.get(option.dest)
            if isinstance(default, basestring):
                opt_str = option.get_opt_string()
                defaults[option.dest] = option.check_value(opt_str, default)
        return optparse.Values(defaults)


def main():
    parser = ConfigOptionParser(
        version=virtualenv_version, usage="%prog [OPTIONS] DEST_DIR", formatter=UpdatingDefaultsHelpFormatter()
    )

    parser.add_option("-v", "--verbose", action="count", dest="verbose", default=0, help="Increase verbosity.")

    parser.add_option("-q", "--quiet", action="count", dest="quiet", default=0, help="Decrease verbosity.")

    parser.add_option(
        "-p",
        "--python",
        dest="python",
        metavar="PYTHON_EXE",
        help="The Python interpreter to use, e.g., --python=python3.5 will use the python3.5 "
        "interpreter to create the new environment.  The default is the interpreter that "
        "virtualenv was installed with (%s)" % sys.executable,
    )

    parser.add_option(
        "--clear", dest="clear", action="store_true", help="Clear out the non-root install and start from scratch."
    )

    parser.set_defaults(system_site_packages=False)
    parser.add_option(
        "--no-site-packages",
        dest="system_site_packages",
        action="store_false",
        help="DEPRECATED. Retained only for backward compatibility. "
        "Not having access to global site-packages is now the default behavior.",
    )

    parser.add_option(
        "--system-site-packages",
        dest="system_site_packages",
        action="store_true",
        help="Give the virtual environment access to the global site-packages.",
    )

    parser.add_option(
        "--always-copy",
        dest="symlink",
        action="store_false",
        default=True,
        help="Always copy files rather than symlinking.",
    )

    parser.add_option(
        "--relocatable",
        dest="relocatable",
        action="store_true",
        help="Make an EXISTING virtualenv environment relocatable. "
        "This fixes up scripts and makes all .pth files relative.",
    )

    parser.add_option(
        "--no-setuptools",
        dest="no_setuptools",
        action="store_true",
        help="Do not install setuptools in the new virtualenv.",
    )

    parser.add_option("--no-pip", dest="no_pip", action="store_true", help="Do not install pip in the new virtualenv.")

    parser.add_option(
        "--no-wheel", dest="no_wheel", action="store_true", help="Do not install wheel in the new virtualenv."
    )

    default_search_dirs = file_search_dirs()
    parser.add_option(
        "--extra-search-dir",
        dest="search_dirs",
        action="append",
        metavar="DIR",
        default=default_search_dirs,
        help="Directory to look for setuptools/pip distributions in. " "This option can be used multiple times.",
    )

    parser.add_option(
        "--download",
        dest="download",
        default=True,
        action="store_true",
        help="Download preinstalled packages from PyPI.",
    )

    parser.add_option(
        "--no-download",
        "--never-download",
        dest="download",
        action="store_false",
        help="Do not download preinstalled packages from PyPI.",
    )

    parser.add_option("--prompt", dest="prompt", help="Provides an alternative prompt prefix for this environment.")

    parser.add_option(
        "--setuptools",
        dest="setuptools",
        action="store_true",
        help="DEPRECATED. Retained only for backward compatibility. This option has no effect.",
    )

    parser.add_option(
        "--distribute",
        dest="distribute",
        action="store_true",
        help="DEPRECATED. Retained only for backward compatibility. This option has no effect.",
    )

    parser.add_option(
        "--unzip-setuptools",
        action="store_true",
        help="DEPRECATED.  Retained only for backward compatibility. This option has no effect.",
    )

    if "extend_parser" in globals():
        extend_parser(parser)  # noqa: F821

    options, args = parser.parse_args()

    global logger

    if "adjust_options" in globals():
        adjust_options(options, args)  # noqa: F821

    verbosity = options.verbose - options.quiet
    logger = Logger([(Logger.level_for_integer(2 - verbosity), sys.stdout)])

    if options.python and not os.environ.get("VIRTUALENV_INTERPRETER_RUNNING"):
        env = os.environ.copy()
        interpreter = resolve_interpreter(options.python)
        if interpreter == sys.executable:
            logger.warn("Already using interpreter %s" % interpreter)
        else:
            logger.notify("Running virtualenv with interpreter %s" % interpreter)
            env["VIRTUALENV_INTERPRETER_RUNNING"] = "true"
            file = __file__
            if file.endswith(".pyc"):
                file = file[:-1]
            popen = subprocess.Popen([interpreter, file] + sys.argv[1:], env=env)
            raise SystemExit(popen.wait())

    if not args:
        print("You must provide a DEST_DIR")
        parser.print_help()
        sys.exit(2)
    if len(args) > 1:
        print("There must be only one argument: DEST_DIR (you gave %s)" % (" ".join(args)))
        parser.print_help()
        sys.exit(2)

    home_dir = args[0]

    if os.path.exists(home_dir) and os.path.isfile(home_dir):
        logger.fatal("ERROR: File already exists and is not a directory.")
        logger.fatal("Please provide a different path or delete the file.")
        sys.exit(3)

    if os.environ.get("WORKING_ENV"):
        logger.fatal("ERROR: you cannot run virtualenv while in a workingenv")
        logger.fatal("Please deactivate your workingenv, then re-run this script")
        sys.exit(3)

    if "PYTHONHOME" in os.environ:
        logger.warn("PYTHONHOME is set.  You *must* activate the virtualenv before using it")
        del os.environ["PYTHONHOME"]

    if options.relocatable:
        make_environment_relocatable(home_dir)
        return

    create_environment(
        home_dir,
        site_packages=options.system_site_packages,
        clear=options.clear,
        prompt=options.prompt,
        search_dirs=options.search_dirs,
        download=options.download,
        no_setuptools=options.no_setuptools,
        no_pip=options.no_pip,
        no_wheel=options.no_wheel,
        symlink=options.symlink,
    )
    if "after_install" in globals():
        after_install(options, home_dir)  # noqa: F821


def call_subprocess(
    cmd,
    show_stdout=True,
    filter_stdout=None,
    cwd=None,
    raise_on_returncode=True,
    extra_env=None,
    remove_from_env=None,
    stdin=None,
):
    cmd_parts = []
    for part in cmd:
        if len(part) > 45:
            part = part[:20] + "..." + part[-20:]
        if " " in part or "\n" in part or '"' in part or "'" in part:
            part = '"%s"' % part.replace('"', '\\"')
        if hasattr(part, "decode"):
            try:
                part = part.decode(sys.getdefaultencoding())
            except UnicodeDecodeError:
                part = part.decode(sys.getfilesystemencoding())
        cmd_parts.append(part)
    cmd_desc = " ".join(cmd_parts)
    if show_stdout:
        stdout = None
    else:
        stdout = subprocess.PIPE
    logger.debug("Running command %s" % cmd_desc)
    if extra_env or remove_from_env:
        env = os.environ.copy()
        if extra_env:
            env.update(extra_env)
        if remove_from_env:
            for varname in remove_from_env:
                env.pop(varname, None)
    else:
        env = None
    try:
        proc = subprocess.Popen(
            cmd,
            stderr=subprocess.STDOUT,
            stdin=None if stdin is None else subprocess.PIPE,
            stdout=stdout,
            cwd=cwd,
            env=env,
        )
    except Exception:
        e = sys.exc_info()[1]
        logger.fatal("Error {} while executing command {}".format(e, cmd_desc))
        raise
    all_output = []
    if stdout is not None:
        if stdin is not None:
            proc.stdin.write(stdin)
            proc.stdin.close()

        stdout = proc.stdout
        encoding = sys.getdefaultencoding()
        fs_encoding = sys.getfilesystemencoding()
        while 1:
            line = stdout.readline()
            try:
                line = line.decode(encoding)
            except UnicodeDecodeError:
                line = line.decode(fs_encoding)
            if not line:
                break
            line = line.rstrip()
            all_output.append(line)
            if filter_stdout:
                level = filter_stdout(line)
                if isinstance(level, tuple):
                    level, line = level
                logger.log(level, line)
                if not logger.stdout_level_matches(level):
                    logger.show_progress()
            else:
                logger.info(line)
    else:
        proc.communicate(stdin)
    proc.wait()
    if proc.returncode:
        if raise_on_returncode:
            if all_output:
                logger.notify("Complete output from command %s:" % cmd_desc)
                logger.notify("\n".join(all_output) + "\n----------------------------------------")
            raise OSError("Command {} failed with error code {}".format(cmd_desc, proc.returncode))
        else:
            logger.warn("Command {} had error code {}".format(cmd_desc, proc.returncode))


def filter_install_output(line):
    if line.strip().startswith("running"):
        return Logger.INFO
    return Logger.DEBUG


def find_wheels(projects, search_dirs):
    """Find wheels from which we can import PROJECTS.

    Scan through SEARCH_DIRS for a wheel for each PROJECT in turn. Return
    a list of the first wheel found for each PROJECT
    """

    wheels = []

    # Look through SEARCH_DIRS for the first suitable wheel. Don't bother
    # about version checking here, as this is simply to get something we can
    # then use to install the correct version.
    for project in projects:
        for dirname in search_dirs:
            # This relies on only having "universal" wheels available.
            # The pattern could be tightened to require -py2.py3-none-any.whl.
            files = glob.glob(os.path.join(dirname, project + "-*.whl"))
            if files:
                wheels.append(os.path.abspath(files[0]))
                break
        else:
            # We're out of luck, so quit with a suitable error
            logger.fatal("Cannot find a wheel for {}".format(project))

    return wheels


def install_wheel(project_names, py_executable, search_dirs=None, download=False):
    if search_dirs is None:
        search_dirs = file_search_dirs()

    wheels = find_wheels(["setuptools", "pip"], search_dirs)
    python_path = os.pathsep.join(wheels)

    # PIP_FIND_LINKS uses space as the path separator and thus cannot have paths
    # with spaces in them. Convert any of those to local file:// URL form.
    try:
        from urlparse import urljoin
        from urllib import pathname2url
    except ImportError:
        from urllib.parse import urljoin
        from urllib.request import pathname2url

    def space_path2url(p):
        if " " not in p:
            return p
        return urljoin("file:", pathname2url(os.path.abspath(p)))

    findlinks = " ".join(space_path2url(d) for d in search_dirs)
    SCRIPT = textwrap.dedent(
        """
        import sys
        import pkgutil
        import tempfile
        import os

        try:
            from pip._internal import main as _main
            cert_data = pkgutil.get_data("pip._vendor.certifi", "cacert.pem")
        except ImportError:
            from pip import main as _main
            cert_data = pkgutil.get_data("pip._vendor.requests", "cacert.pem")

        if cert_data is not None:
            cert_file = tempfile.NamedTemporaryFile(delete=False)
            cert_file.write(cert_data)
            cert_file.close()
        else:
            cert_file = None

        try:
            args = ["install", "--ignore-installed"]
            if cert_file is not None:
                args += ["--cert", cert_file.name{}]
            args += sys.argv[1:]

            sys.exit(_main(args))
        finally:
            if cert_file is not None:
                os.remove(cert_file.name)
    """.format(
            ", '--no-cache'" if is_jython else ""
        )
    ).encode("utf8")

    cmd = [py_executable, "-"] + project_names
    logger.start_progress("Installing %s..." % (", ".join(project_names)))
    logger.indent += 2

    env = {
        "PYTHONPATH": python_path,
        "JYTHONPATH": python_path,  # for Jython < 3.x
        "PIP_FIND_LINKS": findlinks,
        "PIP_USE_WHEEL": "1",
        "PIP_ONLY_BINARY": ":all:",
        "PIP_USER": "0",
        "PIP_NO_INPUT": "1",
    }

    if not download:
        env["PIP_NO_INDEX"] = "1"

    try:
        call_subprocess(cmd, show_stdout=False, extra_env=env, stdin=SCRIPT)
    finally:
        logger.indent -= 2
        logger.end_progress()


def create_environment(
    home_dir,
    site_packages=False,
    clear=False,
    prompt=None,
    search_dirs=None,
    download=False,
    no_setuptools=False,
    no_pip=False,
    no_wheel=False,
    symlink=True,
):
    """
    Creates a new environment in ``home_dir``.

    If ``site_packages`` is true, then the global ``site-packages/``
    directory will be on the path.

    If ``clear`` is true (default False) then the environment will
    first be cleared.
    """
    home_dir, lib_dir, inc_dir, bin_dir = path_locations(home_dir)

    py_executable = os.path.abspath(
        install_python(home_dir, lib_dir, inc_dir, bin_dir, site_packages=site_packages, clear=clear, symlink=symlink)
    )

    install_distutils(home_dir)

    to_install = []

    if not no_setuptools:
        to_install.append("setuptools")

    if not no_pip:
        to_install.append("pip")

    if not no_wheel:
        to_install.append("wheel")

    if to_install:
        install_wheel(to_install, py_executable, search_dirs, download=download)

    install_activate(home_dir, bin_dir, prompt)

    install_python_config(home_dir, bin_dir, prompt)


def is_executable_file(fpath):
    return os.path.isfile(fpath) and os.access(fpath, os.X_OK)


def path_locations(home_dir, dry_run=False):
    """Return the path locations for the environment (where libraries are,
    where scripts go, etc)"""
    home_dir = os.path.abspath(home_dir)
    # XXX: We'd use distutils.sysconfig.get_python_inc/lib but its
    # prefix arg is broken: http://bugs.python.org/issue3386
    if is_win:
        # Windows has lots of problems with executables with spaces in
        # the name; this function will remove them (using the ~1
        # format):
        if not dry_run:
            mkdir(home_dir)
        if " " in home_dir:
            import ctypes

            GetShortPathName = ctypes.windll.kernel32.GetShortPathNameW
            size = max(len(home_dir) + 1, 256)
            buf = ctypes.create_unicode_buffer(size)
            try:
                u = unicode
            except NameError:
                u = str
            ret = GetShortPathName(u(home_dir), buf, size)
            if not ret:
                print('Error: the path "%s" has a space in it' % home_dir)
                print("We could not determine the short pathname for it.")
                print("Exiting.")
                sys.exit(3)
            home_dir = str(buf.value)
        lib_dir = join(home_dir, "Lib")
        inc_dir = join(home_dir, "Include")
        bin_dir = join(home_dir, "Scripts")
    if is_jython:
        lib_dir = join(home_dir, "Lib")
        inc_dir = join(home_dir, "Include")
        bin_dir = join(home_dir, "bin")
    elif is_pypy:
        lib_dir = home_dir
        inc_dir = join(home_dir, "include")
        bin_dir = join(home_dir, "bin")
    elif not is_win:
        lib_dir = join(home_dir, "lib", py_version)
        inc_dir = join(home_dir, "include", py_version + abiflags)
        bin_dir = join(home_dir, "bin")
    return home_dir, lib_dir, inc_dir, bin_dir


def change_prefix(filename, dst_prefix):
    prefixes = [sys.prefix]

    if is_darwin:
        prefixes.extend(
            (
                os.path.join("/Library/Python", sys.version[:3], "site-packages"),
                os.path.join(sys.prefix, "Extras", "lib", "python"),
                os.path.join("~", "Library", "Python", sys.version[:3], "site-packages"),
                # Python 2.6 no-frameworks
                os.path.join("~", ".local", "lib", "python", sys.version[:3], "site-packages"),
                # System Python 2.7 on OSX Mountain Lion
                os.path.join("~", "Library", "Python", sys.version[:3], "lib", "python", "site-packages"),
            )
        )

    if hasattr(sys, "real_prefix"):
        prefixes.append(sys.real_prefix)
    if hasattr(sys, "base_prefix"):
        prefixes.append(sys.base_prefix)
    prefixes = list(map(os.path.expanduser, prefixes))
    prefixes = list(map(os.path.abspath, prefixes))
    # Check longer prefixes first so we don't split in the middle of a filename
    prefixes = sorted(prefixes, key=len, reverse=True)
    filename = os.path.abspath(filename)
    # On Windows, make sure drive letter is uppercase
    if is_win and filename[0] in "abcdefghijklmnopqrstuvwxyz":
        filename = filename[0].upper() + filename[1:]
    for i, prefix in enumerate(prefixes):
        if is_win and prefix[0] in "abcdefghijklmnopqrstuvwxyz":
            prefixes[i] = prefix[0].upper() + prefix[1:]
    for src_prefix in prefixes:
        if filename.startswith(src_prefix):
            _, relpath = filename.split(src_prefix, 1)
            if src_prefix != os.sep:  # sys.prefix == "/"
                assert relpath[0] == os.sep
                relpath = relpath[1:]
            return join(dst_prefix, relpath)
    assert False, "Filename {} does not start with any of these prefixes: {}".format(filename, prefixes)


def copy_required_modules(dst_prefix, symlink):
    import imp

    for modname in REQUIRED_MODULES:
        if modname in sys.builtin_module_names:
            logger.info("Ignoring built-in bootstrap module: %s" % modname)
            continue
        try:
            f, filename, _ = imp.find_module(modname)
        except ImportError:
            logger.info("Cannot import bootstrap module: %s" % modname)
        else:
            if f is not None:
                f.close()
            # special-case custom readline.so on OS X, but not for pypy:
            if (
                modname == "readline"
                and sys.platform == "darwin"
                and not (is_pypy or filename.endswith(join("lib-dynload", "readline.so")))
            ):
                dst_filename = join(dst_prefix, "lib", "python%s" % sys.version[:3], "readline.so")
            elif modname == "readline" and sys.platform == "win32":
                # special-case for Windows, where readline is not a
                # standard module, though it may have been installed in
                # site-packages by a third-party package
                pass
            else:
                dst_filename = change_prefix(filename, dst_prefix)
            copyfile(filename, dst_filename, symlink)
            if filename.endswith(".pyc"):
                pyfile = filename[:-1]
                if os.path.exists(pyfile):
                    copyfile(pyfile, dst_filename[:-1], symlink)


def copy_tcltk(src, dest, symlink):
    """ copy tcl/tk libraries on Windows (issue #93) """
    for libversion in "8.5", "8.6":
        for libname in "tcl", "tk":
            srcdir = join(src, "tcl", libname + libversion)
            destdir = join(dest, "tcl", libname + libversion)
            # Only copy the dirs from the above combinations that exist
            if os.path.exists(srcdir) and not os.path.exists(destdir):
                copyfileordir(srcdir, destdir, symlink)


def subst_path(prefix_path, prefix, home_dir):
    prefix_path = os.path.normpath(prefix_path)
    prefix = os.path.normpath(prefix)
    home_dir = os.path.normpath(home_dir)
    if not prefix_path.startswith(prefix):
        logger.warn("Path not in prefix %r %r", prefix_path, prefix)
        return
    return prefix_path.replace(prefix, home_dir, 1)


def install_python(home_dir, lib_dir, inc_dir, bin_dir, site_packages, clear, symlink=True):
    """Install just the base environment, no distutils patches etc"""
    if sys.executable.startswith(bin_dir):
        print("Please use the *system* python to run this script")
        return

    if clear:
        rmtree(lib_dir)
        # FIXME: why not delete it?
        # Maybe it should delete everything with #!/path/to/venv/python in it
        logger.notify("Not deleting %s", bin_dir)

    if hasattr(sys, "real_prefix"):
        logger.notify("Using real prefix %r" % sys.real_prefix)
        prefix = sys.real_prefix
    elif hasattr(sys, "base_prefix"):
        logger.notify("Using base prefix %r" % sys.base_prefix)
        prefix = sys.base_prefix
    else:
        prefix = sys.prefix
    prefix = os.path.abspath(prefix)
    mkdir(lib_dir)
    fix_lib64(lib_dir, symlink)
    stdlib_dirs = [os.path.dirname(os.__file__)]
    if is_win:
        stdlib_dirs.append(join(os.path.dirname(stdlib_dirs[0]), "DLLs"))
    elif is_darwin:
        stdlib_dirs.append(join(stdlib_dirs[0], "site-packages"))
    if hasattr(os, "symlink"):
        logger.info("Symlinking Python bootstrap modules")
    else:
        logger.info("Copying Python bootstrap modules")
    logger.indent += 2
    try:
        # copy required files...
        for stdlib_dir in stdlib_dirs:
            if not os.path.isdir(stdlib_dir):
                continue
            for fn in os.listdir(stdlib_dir):
                bn = os.path.splitext(fn)[0]
                if fn != "site-packages" and bn in REQUIRED_FILES:
                    copyfile(join(stdlib_dir, fn), join(lib_dir, fn), symlink)
        # ...and modules
        copy_required_modules(home_dir, symlink)
    finally:
        logger.indent -= 2
    # ...copy tcl/tk
    if is_win:
        copy_tcltk(prefix, home_dir, symlink)
    mkdir(join(lib_dir, "site-packages"))
    import site

    site_filename = site.__file__
    if site_filename.endswith(".pyc") or site_filename.endswith(".pyo"):
        site_filename = site_filename[:-1]
    elif site_filename.endswith("$py.class"):
        site_filename = site_filename.replace("$py.class", ".py")
    site_filename_dst = change_prefix(site_filename, home_dir)
    site_dir = os.path.dirname(site_filename_dst)
    writefile(site_filename_dst, SITE_PY)
    writefile(join(site_dir, "orig-prefix.txt"), prefix)
    site_packages_filename = join(site_dir, "no-global-site-packages.txt")
    if not site_packages:
        writefile(site_packages_filename, "")

    if is_pypy or is_win:
        stdinc_dir = join(prefix, "include")
    else:
        stdinc_dir = join(prefix, "include", py_version + abiflags)
    if os.path.exists(stdinc_dir):
        copyfile(stdinc_dir, inc_dir, symlink)
    else:
        logger.debug("No include dir %s" % stdinc_dir)

    platinc_dir = distutils.sysconfig.get_python_inc(plat_specific=1)
    if platinc_dir != stdinc_dir:
        platinc_dest = distutils.sysconfig.get_python_inc(plat_specific=1, prefix=home_dir)
        if platinc_dir == platinc_dest:
            # Do platinc_dest manually due to a CPython bug;
            # not http://bugs.python.org/issue3386 but a close cousin
            platinc_dest = subst_path(platinc_dir, prefix, home_dir)
        if platinc_dest:
            # PyPy's stdinc_dir and prefix are relative to the original binary
            # (traversing virtualenvs), whereas the platinc_dir is relative to
            # the inner virtualenv and ignores the prefix argument.
            # This seems more evolved than designed.
            copyfile(platinc_dir, platinc_dest, symlink)

    # pypy never uses exec_prefix, just ignore it
    if sys.exec_prefix != prefix and not is_pypy:
        if is_win:
            exec_dir = join(sys.exec_prefix, "lib")
        elif is_jython:
            exec_dir = join(sys.exec_prefix, "Lib")
        else:
            exec_dir = join(sys.exec_prefix, "lib", py_version)
        if os.path.isdir(exec_dir):
            for fn in os.listdir(exec_dir):
                copyfile(join(exec_dir, fn), join(lib_dir, fn), symlink)

    if is_jython:
        # Jython has either jython-dev.jar and javalib/ dir, or just
        # jython.jar
        for name in "jython-dev.jar", "javalib", "jython.jar":
            src = join(prefix, name)
            if os.path.exists(src):
                copyfile(src, join(home_dir, name), symlink)
        # XXX: registry should always exist after Jython 2.5rc1
        src = join(prefix, "registry")
        if os.path.exists(src):
            copyfile(src, join(home_dir, "registry"), symlink=False)
        copyfile(join(prefix, "cachedir"), join(home_dir, "cachedir"), symlink=False)

    mkdir(bin_dir)
    py_executable = join(bin_dir, os.path.basename(sys.executable))
    if "Python.framework" in prefix:
        # OS X framework builds cause validation to break
        # https://github.com/pypa/virtualenv/issues/322
        if os.environ.get("__PYVENV_LAUNCHER__"):
            del os.environ["__PYVENV_LAUNCHER__"]
        if re.search(r"/Python(?:-32|-64)*$", py_executable):
            # The name of the python executable is not quite what
            # we want, rename it.
            py_executable = os.path.join(os.path.dirname(py_executable), "python")

    logger.notify("New %s executable in %s", expected_exe, py_executable)
    pcbuild_dir = os.path.dirname(sys.executable)
    pyd_pth = os.path.join(lib_dir, "site-packages", "virtualenv_builddir_pyd.pth")
    if is_win and os.path.exists(os.path.join(pcbuild_dir, "build.bat")):
        logger.notify("Detected python running from build directory %s", pcbuild_dir)
        logger.notify("Writing .pth file linking to build directory for *.pyd files")
        writefile(pyd_pth, pcbuild_dir)
    else:
        pcbuild_dir = None
        if os.path.exists(pyd_pth):
            logger.info("Deleting %s (not Windows env or not build directory python)" % pyd_pth)
            os.unlink(pyd_pth)

    if sys.executable != py_executable:
        # FIXME: could I just hard link?
        executable = sys.executable
        shutil.copyfile(executable, py_executable)
        make_exe(py_executable)
        if is_win or is_cygwin:
            pythonw = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
            if os.path.exists(pythonw):
                logger.info("Also created pythonw.exe")
                shutil.copyfile(pythonw, os.path.join(os.path.dirname(py_executable), "pythonw.exe"))
            python_d = os.path.join(os.path.dirname(sys.executable), "python_d.exe")
            python_d_dest = os.path.join(os.path.dirname(py_executable), "python_d.exe")
            if os.path.exists(python_d):
                logger.info("Also created python_d.exe")
                shutil.copyfile(python_d, python_d_dest)
            elif os.path.exists(python_d_dest):
                logger.info("Removed python_d.exe as it is no longer at the source")
                os.unlink(python_d_dest)

            # we need to copy the DLL to enforce that windows will load the correct one.
            # may not exist if we are cygwin.
            if is_pypy:
                py_executable_dlls = [("libpypy-c.dll", "libpypy_d-c.dll")]
            else:
                py_executable_dlls = [
                    ("python%s.dll" % (sys.version_info[0]), "python%s_d.dll" % (sys.version_info[0])),
                    (
                        "python{}{}.dll".format(sys.version_info[0], sys.version_info[1]),
                        "python{}{}_d.dll".format(sys.version_info[0], sys.version_info[1]),
                    ),
                ]

            for py_executable_dll, py_executable_dll_d in py_executable_dlls:
                pythondll = os.path.join(os.path.dirname(sys.executable), py_executable_dll)
                pythondll_d = os.path.join(os.path.dirname(sys.executable), py_executable_dll_d)
                pythondll_d_dest = os.path.join(os.path.dirname(py_executable), py_executable_dll_d)
                if os.path.exists(pythondll):
                    logger.info("Also created %s" % py_executable_dll)
                    shutil.copyfile(pythondll, os.path.join(os.path.dirname(py_executable), py_executable_dll))
                if os.path.exists(pythondll_d):
                    logger.info("Also created %s" % py_executable_dll_d)
                    shutil.copyfile(pythondll_d, pythondll_d_dest)
                elif os.path.exists(pythondll_d_dest):
                    logger.info("Removed %s as the source does not exist" % pythondll_d_dest)
                    os.unlink(pythondll_d_dest)
        if is_pypy:
            # make a symlink python --> pypy-c
            python_executable = os.path.join(os.path.dirname(py_executable), "python")
            if sys.platform in ("win32", "cygwin"):
                python_executable += ".exe"
            logger.info("Also created executable %s" % python_executable)
            copyfile(py_executable, python_executable, symlink)

            if is_win:
                for name in ["libexpat.dll", "libeay32.dll", "ssleay32.dll", "sqlite3.dll", "tcl85.dll", "tk85.dll"]:
                    src = join(prefix, name)
                    if os.path.exists(src):
                        copyfile(src, join(bin_dir, name), symlink)

                for d in sys.path:
                    if d.endswith("lib_pypy"):
                        break
                else:
                    logger.fatal("Could not find lib_pypy in sys.path")
                    raise SystemExit(3)
                logger.info("Copying lib_pypy")
                copyfile(d, os.path.join(home_dir, "lib_pypy"), symlink)

    if os.path.splitext(os.path.basename(py_executable))[0] != expected_exe:
        secondary_exe = os.path.join(os.path.dirname(py_executable), expected_exe)
        py_executable_ext = os.path.splitext(py_executable)[1]
        if py_executable_ext.lower() == ".exe":
            # python2.4 gives an extension of '.4' :P
            secondary_exe += py_executable_ext
        if os.path.exists(secondary_exe):
            logger.warn(
                "Not overwriting existing {} script {} (you must use {})".format(
                    expected_exe, secondary_exe, py_executable
                )
            )
        else:
            logger.notify("Also creating executable in %s" % secondary_exe)
            shutil.copyfile(sys.executable, secondary_exe)
            make_exe(secondary_exe)

    if ".framework" in prefix:
        if "Python.framework" in prefix:
            logger.debug("MacOSX Python framework detected")
            # Make sure we use the embedded interpreter inside
            # the framework, even if sys.executable points to
            # the stub executable in ${sys.prefix}/bin
            # See http://groups.google.com/group/python-virtualenv/
            #                              browse_thread/thread/17cab2f85da75951
            original_python = os.path.join(prefix, "Resources/Python.app/Contents/MacOS/Python")
        if "EPD" in prefix:
            logger.debug("EPD framework detected")
            original_python = os.path.join(prefix, "bin/python")
        shutil.copy(original_python, py_executable)

        # Copy the framework's dylib into the virtual
        # environment
        virtual_lib = os.path.join(home_dir, ".Python")

        if os.path.exists(virtual_lib):
            os.unlink(virtual_lib)
        copyfile(os.path.join(prefix, "Python"), virtual_lib, symlink)

        # And then change the install_name of the copied python executable
        try:
            mach_o_change(py_executable, os.path.join(prefix, "Python"), "@executable_path/../.Python")
        except Exception:
            e = sys.exc_info()[1]
            logger.warn("Could not call mach_o_change: %s. " "Trying to call install_name_tool instead." % e)
            try:
                call_subprocess(
                    [
                        "install_name_tool",
                        "-change",
                        os.path.join(prefix, "Python"),
                        "@executable_path/../.Python",
                        py_executable,
                    ]
                )
            except Exception:
                logger.fatal("Could not call install_name_tool -- you must " "have Apple's development tools installed")
                raise

    if not is_win:
        # Ensure that 'python', 'pythonX' and 'pythonX.Y' all exist
        py_exe_version_major = "python%s" % sys.version_info[0]
        py_exe_version_major_minor = "python{}.{}".format(sys.version_info[0], sys.version_info[1])
        py_exe_no_version = "python"
        required_symlinks = [py_exe_no_version, py_exe_version_major, py_exe_version_major_minor]

        py_executable_base = os.path.basename(py_executable)

        if py_executable_base in required_symlinks:
            # Don't try to symlink to yourself.
            required_symlinks.remove(py_executable_base)

        for pth in required_symlinks:
            full_pth = join(bin_dir, pth)
            if os.path.exists(full_pth):
                os.unlink(full_pth)
            if symlink:
                os.symlink(py_executable_base, full_pth)
            else:
                copyfile(py_executable, full_pth, symlink)

    cmd = [
        py_executable,
        "-c",
        "import sys;out=sys.stdout;" 'getattr(out, "buffer", out).write(sys.prefix.encode("utf-8"))',
    ]
    logger.info('Testing executable with %s %s "%s"' % tuple(cmd))
    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE)
        proc_stdout, proc_stderr = proc.communicate()
    except OSError:
        e = sys.exc_info()[1]
        if e.errno == errno.EACCES:
            logger.fatal("ERROR: The executable {} could not be run: {}".format(py_executable, e))
            sys.exit(100)
        else:
            raise e

    proc_stdout = proc_stdout.strip().decode("utf-8")
    proc_stdout = os.path.normcase(os.path.abspath(proc_stdout))
    norm_home_dir = os.path.normcase(os.path.abspath(home_dir))
    if hasattr(norm_home_dir, "decode"):
        norm_home_dir = norm_home_dir.decode(sys.getfilesystemencoding())
    if proc_stdout != norm_home_dir:
        logger.fatal("ERROR: The executable %s is not functioning" % py_executable)
        logger.fatal("ERROR: It thinks sys.prefix is {!r} (should be {!r})".format(proc_stdout, norm_home_dir))
        logger.fatal("ERROR: virtualenv is not compatible with this system or executable")
        if is_win:
            logger.fatal(
                "Note: some Windows users have reported this error when they "
                'installed Python for "Only this user" or have multiple '
                "versions of Python installed. Copying the appropriate "
                "PythonXX.dll to the virtualenv Scripts/ directory may fix "
                "this problem."
            )
        sys.exit(100)
    else:
        logger.info("Got sys.prefix result: %r" % proc_stdout)

    pydistutils = os.path.expanduser("~/.pydistutils.cfg")
    if os.path.exists(pydistutils):
        logger.notify("Please make sure you remove any previous custom paths from " "your %s file." % pydistutils)
    # FIXME: really this should be calculated earlier

    fix_local_scheme(home_dir, symlink)

    if site_packages:
        if os.path.exists(site_packages_filename):
            logger.info("Deleting %s" % site_packages_filename)
            os.unlink(site_packages_filename)

    return py_executable


def install_activate(home_dir, bin_dir, prompt=None):
    if is_win or is_jython and os._name == "nt":
        files = {"activate.bat": ACTIVATE_BAT, "deactivate.bat": DEACTIVATE_BAT, "activate.ps1": ACTIVATE_PS}

        # MSYS needs paths of the form /c/path/to/file
        drive, tail = os.path.splitdrive(home_dir.replace(os.sep, "/"))
        home_dir_msys = (drive and "/%s%s" or "%s%s") % (drive[:1], tail)

        # Run-time conditional enables (basic) Cygwin compatibility
        home_dir_sh = """$(if [ "$OSTYPE" "==" "cygwin" ]; then cygpath -u '{}'; else echo '{}'; fi;)""".format(
            home_dir, home_dir_msys
        )
        files["activate"] = ACTIVATE_SH.replace("__VIRTUAL_ENV__", home_dir_sh)

    else:
        files = {"activate": ACTIVATE_SH}

        # suppling activate.fish in addition to, not instead of, the
        # bash script support.
        files["activate.fish"] = ACTIVATE_FISH

        # same for csh/tcsh support...
        files["activate.csh"] = ACTIVATE_CSH

        # same for powershell
        files["activate.ps1"] = ACTIVATE_PS

    files["activate_this.py"] = ACTIVATE_THIS

    install_files(home_dir, bin_dir, prompt, files)


def install_files(home_dir, bin_dir, prompt, files):
    if hasattr(home_dir, "decode"):
        home_dir = home_dir.decode(sys.getfilesystemencoding())
    vname = os.path.basename(home_dir)
    for name, content in files.items():
        content = content.replace("__VIRTUAL_PROMPT__", prompt or "")
        content = content.replace("__VIRTUAL_WINPROMPT__", prompt or "(%s)" % vname)
        content = content.replace("__VIRTUAL_ENV__", home_dir)
        content = content.replace("__VIRTUAL_NAME__", vname)
        content = content.replace("__BIN_NAME__", os.path.basename(bin_dir))
        content = content.replace("__PATH_SEP__", os.pathsep)
        writefile(os.path.join(bin_dir, name), content)


def install_python_config(home_dir, bin_dir, prompt=None):
    if sys.platform == "win32" or is_jython and os._name == "nt":
        files = {}
    else:
        files = {"python-config": PYTHON_CONFIG}
    install_files(home_dir, bin_dir, prompt, files)
    for name, _ in files.items():
        make_exe(os.path.join(bin_dir, name))


def install_distutils(home_dir):
    distutils_path = change_prefix(distutils.__path__[0], home_dir)
    mkdir(distutils_path)
    # FIXME: maybe this prefix setting should only be put in place if
    # there's a local distutils.cfg with a prefix setting?
    home_dir = os.path.abspath(home_dir)
    # FIXME: this is breaking things, removing for now:
    # distutils_cfg = DISTUTILS_CFG + "\n[install]\nprefix=%s\n" % home_dir
    writefile(os.path.join(distutils_path, "__init__.py"), DISTUTILS_INIT)
    writefile(os.path.join(distutils_path, "distutils.cfg"), DISTUTILS_CFG, overwrite=False)


def fix_local_scheme(home_dir, symlink=True):
    """
    Platforms that use the "posix_local" install scheme (like Ubuntu with
    Python 2.7) need to be given an additional "local" location, sigh.
    """
    try:
        import sysconfig
    except ImportError:
        pass
    else:
        if sysconfig._get_default_scheme() == "posix_local":
            local_path = os.path.join(home_dir, "local")
            if not os.path.exists(local_path):
                os.mkdir(local_path)
                for subdir_name in os.listdir(home_dir):
                    if subdir_name == "local":
                        continue
                    copyfile(
                        os.path.abspath(os.path.join(home_dir, subdir_name)),
                        os.path.join(local_path, subdir_name),
                        symlink,
                    )


def fix_lib64(lib_dir, symlink=True):
    """
    Some platforms (particularly Gentoo on x64) put things in lib64/pythonX.Y
    instead of lib/pythonX.Y.  If this is such a platform we'll just create a
    symlink so lib64 points to lib
    """
    # PyPy's library path scheme is not affected by this.
    # Return early or we will die on the following assert.
    if is_pypy:
        logger.debug("PyPy detected, skipping lib64 symlinking")
        return
    # Check we have a lib64 library path
    if not [p for p in distutils.sysconfig.get_config_vars().values() if isinstance(p, basestring) and "lib64" in p]:
        return

    logger.debug("This system uses lib64; symlinking lib64 to lib")

    assert os.path.basename(lib_dir) == "python%s" % sys.version[:3], "Unexpected python lib dir: %r" % lib_dir
    lib_parent = os.path.dirname(lib_dir)
    top_level = os.path.dirname(lib_parent)
    lib_dir = os.path.join(top_level, "lib")
    lib64_link = os.path.join(top_level, "lib64")
    assert os.path.basename(lib_parent) == "lib", "Unexpected parent dir: %r" % lib_parent
    if os.path.lexists(lib64_link):
        return
    if symlink:
        os.symlink(lib_dir, lib64_link)
    else:
        copyfile(lib_dir, lib64_link)


def resolve_interpreter(exe):
    """
    If the executable given isn't an absolute path, search $PATH for the interpreter
    """
    # If the "executable" is a version number, get the installed executable for
    # that version
    orig_exe = exe
    python_versions = get_installed_pythons()
    if exe in python_versions:
        exe = python_versions[exe]

    if os.path.abspath(exe) != exe:
        exe = distutils.spawn.find_executable(exe) or exe
    if not os.path.exists(exe):
        logger.fatal("The path {} (from --python={}) does not exist".format(exe, orig_exe))
        raise SystemExit(3)
    if not is_executable(exe):
        logger.fatal("The path {} (from --python={}) is not an executable file".format(exe, orig_exe))
        raise SystemExit(3)
    return exe


def is_executable(exe):
    """Checks a file is executable"""
    return os.path.isfile(exe) and os.access(exe, os.X_OK)


# Relocating the environment:
def make_environment_relocatable(home_dir):
    """
    Makes the already-existing environment use relative paths, and takes out
    the #!-based environment selection in scripts.
    """
    home_dir, lib_dir, inc_dir, bin_dir = path_locations(home_dir)
    activate_this = os.path.join(bin_dir, "activate_this.py")
    if not os.path.exists(activate_this):
        logger.fatal(
            "The environment doesn't have a file %s -- please re-run virtualenv "
            "on this environment to update it" % activate_this
        )
    fixup_scripts(home_dir, bin_dir)
    fixup_pth_and_egg_link(home_dir)
    # FIXME: need to fix up distutils.cfg


OK_ABS_SCRIPTS = [
    "python",
    "python%s" % sys.version[:3],
    "activate",
    "activate.bat",
    "activate_this.py",
    "activate.fish",
    "activate.csh",
]


def fixup_scripts(home_dir, bin_dir):
    if is_win:
        new_shebang_args = ("%s /c" % os.path.normcase(os.environ.get("COMSPEC", "cmd.exe")), "", ".exe")
    else:
        new_shebang_args = ("/usr/bin/env", sys.version[:3], "")

    # This is what we expect at the top of scripts:
    shebang = "#!%s" % os.path.normcase(os.path.join(os.path.abspath(bin_dir), "python%s" % new_shebang_args[2]))
    # This is what we'll put:
    new_shebang = "#!%s python%s%s" % new_shebang_args

    for filename in os.listdir(bin_dir):
        filename = os.path.join(bin_dir, filename)
        if not os.path.isfile(filename):
            # ignore subdirs, e.g. .svn ones.
            continue
        lines = None
        with open(filename, "rb") as f:
            try:
                lines = f.read().decode("utf-8").splitlines()
            except UnicodeDecodeError:
                # This is probably a binary program instead
                # of a script, so just ignore it.
                continue
        if not lines:
            logger.warn("Script %s is an empty file" % filename)
            continue

        old_shebang = lines[0].strip()
        old_shebang = old_shebang[0:2] + os.path.normcase(old_shebang[2:])

        if not old_shebang.startswith(shebang):
            if os.path.basename(filename) in OK_ABS_SCRIPTS:
                logger.debug("Cannot make script %s relative" % filename)
            elif lines[0].strip() == new_shebang:
                logger.info("Script %s has already been made relative" % filename)
            else:
                logger.warn(
                    "Script %s cannot be made relative (it's not a normal script that starts with %s)"
                    % (filename, shebang)
                )
            continue
        logger.notify("Making script %s relative" % filename)
        script = relative_script([new_shebang] + lines[1:])
        with open(filename, "wb") as f:
            f.write("\n".join(script).encode("utf-8"))


def relative_script(lines):
    "Return a script that'll work in a relocatable environment."
    activate = (
        "import os; "
        "activate_this=os.path.join(os.path.dirname(os.path.realpath(__file__)), 'activate_this.py'); "
        "exec(compile(open(activate_this).read(), activate_this, 'exec'), dict(__file__=activate_this)); "
        "del os, activate_this"
    )
    # Find the last future statement in the script. If we insert the activation
    # line before a future statement, Python will raise a SyntaxError.
    activate_at = None
    for idx, line in reversed(list(enumerate(lines))):
        if line.split()[:3] == ["from", "__future__", "import"]:
            activate_at = idx + 1
            break
    if activate_at is None:
        # Activate after the shebang.
        activate_at = 1
    return lines[:activate_at] + ["", activate, ""] + lines[activate_at:]


def fixup_pth_and_egg_link(home_dir, sys_path=None):
    """Makes .pth and .egg-link files use relative paths"""
    home_dir = os.path.normcase(os.path.abspath(home_dir))
    if sys_path is None:
        sys_path = sys.path
    for path in sys_path:
        if not path:
            path = "."
        if not os.path.isdir(path):
            continue
        path = os.path.normcase(os.path.abspath(path))
        if not path.startswith(home_dir):
            logger.debug("Skipping system (non-environment) directory %s" % path)
            continue
        for filename in os.listdir(path):
            filename = os.path.join(path, filename)
            if filename.endswith(".pth"):
                if not os.access(filename, os.W_OK):
                    logger.warn("Cannot write .pth file %s, skipping" % filename)
                else:
                    fixup_pth_file(filename)
            if filename.endswith(".egg-link"):
                if not os.access(filename, os.W_OK):
                    logger.warn("Cannot write .egg-link file %s, skipping" % filename)
                else:
                    fixup_egg_link(filename)


def fixup_pth_file(filename):
    lines = []
    prev_lines = []
    with open(filename) as f:
        prev_lines = f.readlines()
    for line in prev_lines:
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("import ") or os.path.abspath(line) != line:
            lines.append(line)
        else:
            new_value = make_relative_path(filename, line)
            if line != new_value:
                logger.debug("Rewriting path {} as {} (in {})".format(line, new_value, filename))
            lines.append(new_value)
    if lines == prev_lines:
        logger.info("No changes to .pth file %s" % filename)
        return
    logger.notify("Making paths in .pth file %s relative" % filename)
    with open(filename, "w") as f:
        f.write("\n".join(lines) + "\n")


def fixup_egg_link(filename):
    with open(filename) as f:
        link = f.readline().strip()
    if os.path.abspath(link) != link:
        logger.debug("Link in %s already relative" % filename)
        return
    new_link = make_relative_path(filename, link)
    logger.notify("Rewriting link {} in {} as {}".format(link, filename, new_link))
    with open(filename, "w") as f:
        f.write(new_link)


def make_relative_path(source, dest, dest_is_directory=True):
    """
    Make a filename relative, where the filename is dest, and it is
    being referred to from the filename source.

        >>> make_relative_path('/usr/share/something/a-file.pth',
        ...                    '/usr/share/another-place/src/Directory')
        '../another-place/src/Directory'
        >>> make_relative_path('/usr/share/something/a-file.pth',
        ...                    '/home/user/src/Directory')
        '../../../home/user/src/Directory'
        >>> make_relative_path('/usr/share/a-file.pth', '/usr/share/')
        './'
    """
    source = os.path.dirname(source)
    if not dest_is_directory:
        dest_filename = os.path.basename(dest)
        dest = os.path.dirname(dest)
    dest = os.path.normpath(os.path.abspath(dest))
    source = os.path.normpath(os.path.abspath(source))
    dest_parts = dest.strip(os.path.sep).split(os.path.sep)
    source_parts = source.strip(os.path.sep).split(os.path.sep)
    while dest_parts and source_parts and dest_parts[0] == source_parts[0]:
        dest_parts.pop(0)
        source_parts.pop(0)
    full_parts = [".."] * len(source_parts) + dest_parts
    if not dest_is_directory:
        full_parts.append(dest_filename)
    if not full_parts:
        # Special case for the current directory (otherwise it'd be '')
        return "./"
    return os.path.sep.join(full_parts)


# Bootstrap script creation:
def create_bootstrap_script(extra_text, python_version=""):
    """
    Creates a bootstrap script, which is like this script but with
    extend_parser, adjust_options, and after_install hooks.

    This returns a string that (written to disk of course) can be used
    as a bootstrap script with your own customizations.  The script
    will be the standard virtualenv.py script, with your extra text
    added (your extra text should be Python code).

    If you include these functions, they will be called:

    ``extend_parser(optparse_parser)``:
        You can add or remove options from the parser here.

    ``adjust_options(options, args)``:
        You can change options here, or change the args (if you accept
        different kinds of arguments, be sure you modify ``args`` so it is
        only ``[DEST_DIR]``).

    ``after_install(options, home_dir)``:

        After everything is installed, this function is called.  This
        is probably the function you are most likely to use.  An
        example would be::

            def after_install(options, home_dir):
                subprocess.call([join(home_dir, 'bin', 'easy_install'),
                                 'MyPackage'])
                subprocess.call([join(home_dir, 'bin', 'my-package-script'),
                                 'setup', home_dir])

        This example immediately installs a package, and runs a setup
        script from that package.

    If you provide something like ``python_version='2.5'`` then the
    script will start with ``#!/usr/bin/env python2.5`` instead of
    ``#!/usr/bin/env python``.  You can use this when the script must
    be run with a particular Python version.
    """
    filename = __file__
    if filename.endswith(".pyc"):
        filename = filename[:-1]
    with codecs.open(filename, "r", encoding="utf-8") as f:
        content = f.read()
    py_exe = "python%s" % python_version
    content = ("#!/usr/bin/env %s\n" % py_exe) + "# WARNING: This file is generated\n" + content
    return content.replace("##EXT" "END##", extra_text)


# EXTEND
def convert(s):
    b = base64.b64decode(s.encode("ascii"))
    return zlib.decompress(b).decode("utf-8")


# file site.py
SITE_PY = convert(
    """
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
Tkg=
"""
)

# file activate.sh
ACTIVATE_SH = convert(
    """
eJytVd9v2kAMfs9fYQLq2m4MscdNVKMqEkgtVIQxbeuUHolpTgsXdHehpT/+9/mSEBJS2MOaB0ji
z77P9menDpOAK5jzEGERKw0zhFihD/dcB2CrKJYewoyLFvM0XzGNNpzOZbSAGVPBqVWHdRSDx4SI
NMhYANfgc4meDteW5ePGC45P4MkCumKhUENzDsu1H3lw1vJx1RJxGMKns6O2lWDqINGgotAHFCsu
I7FAoWHFJGezEFWGqsEvaD5C42naHb93X+A3+elYCgVaxgh8DmQAys9HL2SS0mIaWBgm7mTN/O3G
kzu6vHCng/HkW/fSve5O+hTOpnhfQAcoEry5jKVjNypoO0fgwzKSOgHm79KUK06Jfc7/RebHpD8a
9kdXvT2UcnuFWG6p0stNB0mWUUQ1q3uiGRVEMfXHR03dTuQATPjwqIIPcB9wL4CArRAY/ZHJixYL
Y9YBtcAoLQtFevOoI9QaHcEdMSAB0d08kuZhyUiSmav6CPCdVBnFOjNrLu6yMCWgKRA0TInBC5i4
QwX3JG/mm581GKnSsSSxJTFHf9MAKr8w5T/vOv1mUurn5/zlT6fvTntjZzAaNl9rQ5JkU5KIc0GX
inagwU57T2eddqWlTrvaS6d9sImZeUMkhWysveF0m37NcGub9Dpgi0j4qGiOzATjDr06OBjOYQOo
7RBoGtNm9Denv1i0LVI7lxJDXLHSSBeWRflsyyqw7diuW3h0XdvK6lBMyaoMG1UyHdTsoYBuue75
YOgOu1c91/2cwYpznPPeDoQpGL2xSm09NKp7BsvQ2hnT3aMs07lUnskpxewvBk73/LLnXo9HV9eT
ijB3hWBO2ygoiWg/bKuZxqCCQq0DD3vkWIVvI2KosIw+vqW1gIItEG5KJb+xb09g65ktwYKgTc51
uGJ/EFQs0ayEWLCQM5V9N4g+1+8UbXOJzF8bqhKtIqIwicWvzNFROZJlpfD8A7Vc044R0FxkcezG
VzsV75usvTdYef+57v5n1b225qhXfwEmxHEs
"""
)

# file activate.fish
ACTIVATE_FISH = convert(
    """
eJyFVlFv2zYQftevuMoOnBS1g70WGIZ08RADSRw4boBhGGhGOsUcKFIjKbUu9uN7lCyJsrVWDxZE
fnf38e6+oyew3QsLmZAIeWkdvCKUFlP6EeoNdlaXJkF4FeqaJ05U3OEiE3a/g/dfhNsLBRxMqZQH
+3W4hL1zxcfra/9l9yjlItE5XIFFa4VW7xfRBG41KO28IQgHqTCYOHlYRFFWKoqiFaTYhoN5CrPl
V8JVwriSS1QV5DpF4CoFg640CpwGt0dyanIugRDCaJWjcotZBPRMCGjRgZZpuAsVN4K/SrQ1SmTg
kHIwVxBP2fr+lr2sNtvPN/fs6WZ7F9cY/3hP87ev4FfhHDjEIYwDUKXRz6L+ub1bP96tH5Yjsbu9
Uwbdxo95DGE/YPPH6vmOPW3WD09btn5Zbjar24DPBJ7JO1eAeeEOIHVCBdhNffVZW01WcEcdQ0Xi
UuovdakM5roiqM5gV4MLo8nDrm281tYS891ieBQJ5+6jgNHScItBu8zsSYymc6zTBmsy2og3objs
44ThIbAdAyTAqK9YgPqZBZ5ZjNZqLPPDah3RbVGXjy/DKsZTbt6qv375O4Z3v8JMaZXSsim9tnA2
KKLM5u3eu3HOxSHVyfhWL9eOX81xAp+V5yiMQYkVDyW3iAKRD5lFUdvmwckgZiz4ZCzuYWcSg2kt
tIFS42lgfs3Yp9Uje7x5WJKnI7zju5v2+tj5bNLiImreMP8XTtQzTiNQ6BgeQy91trrp12e6OLg9
LczzZg3qejboTqnfhidjt6vnm0/3y2PnxMcB+LsuDnWzJyUVgwoxlEQXm5NYTrvzKMBBz4ftftbN
A/ioGqjleIUDQlPruCvtB8i0CW0sobi/Jmwh+YFujLNx4MM3xq2TcBw8NSR1hcYIujfIa0Xv9LcA
s8r8jfQB/vF3YGGwoBTX5MLbQvEc+9jhpOw78yhX1k/IuoxGKJfB7MJe2NkoHC7pLCzRks7eXGNX
nQeUFv/H3eWFvYLZiDFcvtIQ9IyH3REHbtsp0qRgMzIQu3R2NsleQ4z+Op72WY/hP2j+KXTA0QE3
nFutYMbG3AnpuuO/AygvqEs=
"""
)

# file activate.csh
ACTIVATE_CSH = convert(
    """
eJx9k9tq20AQhu/3Kf7IJm5N4vRarts6caCBxAnBCZSmLCtpXC1IK2e1svFNn72zklzkA9WFkOb0
z34708Mi1SWWOiPkVekQEaqSEmy0SxGURWVjQqTNlYqdXitHo7hMAwyXtsjBn8OR6OFHUSFWxhQO
tjLQDom2FLts6703ljgvQbTFTK11QphpXGeq1Pic1IYk+vY7VzobxUX+ZSRESQ6GNpk2NBm8iYEQ
KtOqREK7LjBwxN32v8rH+5l8vXtevEzv5dN08R1nE3zC+Tm4CJk1alvQP4oL3wMfVRkvduQdw1Kq
ynSMkzrPjw9Pi64SVsxj5SaHQnXgf6Rq/7hx+W53jtv5aysdvJ2Fw8BrBaYwCZts5SFQW/OITMe6
2iZFzPR6eKm1tbWU0VoZh7WyWkUZlSPRyd1XqC/ioCsEUnZ+pQya6zoiyChazGL/JjrZ4fuVlNd3
czmfPtxKGf7L4Ecv8aGj1ZBiuZpE8BEuJSPAj1fn8tKonDDBqRxBWUkng/e6cV6aTKKXHtlNUWWJ
3wdtoDyZS20c2ZoV+SLaFiYn4y44mGM2qY5TXoOSLtBvxgG8WhUTXfIgJ1CG14qw8XXNwHFWrCxB
RUXl/HHaGeK47Ubx5ngCPHmt9eDEJ8aIiTex/hh1cseAyR8Mg367VWwYdiuG+4RaSebzs7+jFb7/
Qqd+g6mF1Uz2LnK3rfX08dulhcFl3vwL0SyW+At+C2qe
"""
)

# file activate.bat
ACTIVATE_BAT = convert(
    """
eJx9Ul9LhEAQfxf8DoOclI/dYyFkaCmcq4gZQTBUrincuZFbff12T133TM+nnd35/Zvxlr7XDFhV
mUZHOVhFlOWP3g4DUriIWoVomYZpNBWUtGpaWgImO191pFkSpzlcmgaI70jVX7n2Qp8tuByg+46O
CMHbMq64T+nmlJt082D1T44muCDk2prgEHF4mdI9RaS/QwSt3zSyIAaftRccvqVTBziD1x/WlPD5
xd729NDBb8Nr4DU9QNMKsJeH9pkhPedhQsIkDuCDCa6A+NF9IevVFAohkqizdHetg/tkWvPoftWJ
MCqnOxv7/x7Np6yv9P2Ker5dmX8yNyCkkWnbZy3N5LarczlqL8htx2EM9rQ/2H5BvIsIEi8OEG8U
+g8CsNTr
"""
)

# file deactivate.bat
DEACTIVATE_BAT = convert(
    """
eJyFkN0KgkAUhO8X9h0GQapXCIQEDQX/EBO6kso1F9KN3Or1201Si6JzN+fMGT5mxQ61gKgqSijp
mETup9nGDgo3yi29S90QjmhnEteOYb6AFNjdBC9xvoj9iTUd7lzWkDVrwFuYiZ15JiW8QiskSlbx
lpUo4sApXtlJGodJhqNQWW7k+Ou831ACNZrC6BeW+eXPNEbfl7OiXr6H/oHZZl4ceXHoToG0nuIM
pk+k4fAba/wd0Pr4P2CqyLeOlJ4iKfkJo6v/iaH9YzfPMEoeMG2RUA==
"""
)

# file activate.ps1
ACTIVATE_PS = convert(
    """
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
"""
)

# file distutils-init.py
DISTUTILS_INIT = convert(
    """
eJytV21v5DQQ/u5fMaRCJLANcHxBlVYI7g504nSgU7+gqorcxNk1zdrB9m679+uZsfPivGyPD0Sq
5PWMZ8bPPDPjykOrjQN5aJkMS237lT0PyydulFQ7y9gV6LbUlQBpQWkHHE7SuCNvhDrBQVfHRmzA
angSUHIFR4uaDpyGWqoK3F6AdVUjH9DQO2+bK/cF3OIBbR5BK2jP7XmDimj/cLQOHgT6CIZxlzsw
wspKWJCKzKEdtHbdnt1eq29RT9ZSVNfP+Tn/BJU0onTanIfL+dgZQ4HiBwFbvG7ecrfPux0SWXd0
srEF7Ucaf2up0pl6GgzmRVHLRhRFtoFkMJBkTNbDcaXNgRbp1EEG20UQ6eLMYD+7YYBfn4+cFmly
i7BGaRg8QMvLR75DBB18aYG3reDGUjYQ1YAfWMKh0SV3EtHnNmyerROH0dBPeBfRWBG8Fz7yosil
ssK49LsNzC8FV8iOf/gN/Prjq+/9ISN4U4yRbYlzeaN5VYTkpkkxXmFUTDbwQSsx97CBNEER/ZGd
P3//rXjz7uPb17d/fPwry7zDK3it27O/jhGNOCHREAdn5MPRCetVnDmHG4VbGXGSFlEoCgxvGm8e
S/0R8VyK1sHPvcW3xmgzWmu5tR1YJ2EuWx2EjNVGR5BDR1na2FBCSq1quaN7SYuCG/soW8aGKzxw
KyzGonasC+0DZjaKalTAOHBBtYxQlnt4OMqmKsSzg5GcUGlh1VcOHpV+gj3+IWt2wnk8seJsVFze
zp6K9wmLXD9ZuKai33NTUXUESpEKUtDoY9cHvG9R0dXy1ohaPmeMCsb/brirkfxUHAka/eFVEi4x
xSgv9eHAVZWPN+hQGzeQ0RqXwwbzdsoG8zNqpROVbExjJWrqXLyRn0ShW6oRm1rR1JEOfRQ37uaI
jOHmjCnGOsMWRtydatK3VN3C3f1ETTRoEvmmLHbIUqSLI5soodl/c7HYy23bSNe3GyvajLEXjUQV
P2mLlDNP7ZBILMz3SJGkq8T+m4Ccr8PKXkjzanKHH10fCQbmuxFDthBx4SryQquOlfaGMYqWhlYR
Cs93YEKR1PI30oa6x8jzhRbDMRKIM92PmVP7QtjCqpsOi45ZCHWYVlgMrbbyORnzjQPW+DPdPEvy
9hwBV++S0K2G5r16aPXMXGuR8T7ZE8U4aq8uLYnSqdIYC5Y5NgscNjiPGgwi9cAsy4t0cqEq+yRx
IC4iXikBbwhpedAnkdLxjE1FNA9Vla6Eb4Q7GhXUWHgTfCbliM8KDWJ6jS18yjFsqkV4vhRSlVSm
vWI+FXWsGsSzkyk1zcK2osQnULnFEg352VIP6uBBHMPmsjd1+959XMsxHstwp057l1jF7FKYOPMq
XfphuDTXC9klDGJ4ijk8M3vYuC6hSQ/QF9BE8RJNasQVjjSSXkQ3VgJqWf8j3IuopjF9FnzUuQx+
JFwHf4ZmMUezt9eJTzyMnImpSLYKfyRPv+ZmZztgPT6dxRU/ne6Qg5ceEPRhvDTN1lradIg1fogN
56YTeQiK3qaly3y6k/fvfsGHaOL/N8KONihN29OwfdcfuMdo+rjwicftIz6NqDfyphmOzh8FUQjU
OmchoHvC5YLn/jHq19/AXef8fuqdzMaUHI4sSBblY4VlK1J2kRsLnsW8+Rc/zwIT
"""
)

# file distutils.cfg
DISTUTILS_CFG = convert(
    """
eJxNj00KwkAMhfc9xYNuxe4Ft57AjYiUtDO1wXSmNJnK3N5pdSEEAu8nH6lxHVlRhtDHMPATA4uH
xJ4EFmGbvfJiicSHFRzUSISMY6hq3GLCRLnIvSTnEefN0FIjw5tF0Hkk9Q5dRunBsVoyFi24aaLg
9FDOlL0FPGluf4QjcInLlxd6f6rqkgPu/5nHLg0cXCscXoozRrP51DRT3j9QNl99AP53T2Q=
"""
)

# file activate_this.py
ACTIVATE_THIS = convert(
    """
eJyNU8Fu2zAMvesrCA1FbSxzhvUWIIcOGLDDNvTQyxAEhmLTiVZZMiTFif9+pFwnbtFiM2BbFJ8e
+ShSSvl1gGPQdg94xqrRBrN40KHk1QJqXcWsTEZZri+OPIfBHeGkjRGqirpXEYG90Gsfj8qg7YFe
7Z1t0cZCiEf2VsrCDike1nA6oE0s7TFE3gJy4lmHyMk8DPHgLGgb0Xce6bsA66KIB5zH2Gm77BJU
SCmFiH5YCaBnylngucIuwi/V4jfvnR/dXmkKeB8C+qidTZ4sefiRv6e0/NGOuox+wmuFbjsVD8vo
lpP4kkFFN9y+Ltn7yDyXKWAudNs5H8GFaRV0xMt6CEI4U5culMwFawIWz7Ut9hgz+XD/+F0uQMpc
XF2bcXs74vlkUWtvqQzZZKtd4P8lWbrVjxM4YMfGNa7YKarY+2T/JiehDcspOqNi43wL6zXIk7Z3
X+R4K6ybglVPao9hFuuP0zbj+CTyh96xVoZ+mqAkHE3A/ycxI8nYOTdBwk1KrEcfqBs2q7vtGyGo
DfuSYNM1GGrVLOkhOxeC8YWqa/5TNbIXieSCkR6VKYmn0WciSGeTIa5L2uckxQf46XoeKpqLuqZ5
IbY2QHRpq6Ebpo5pksHxV8LiaZ7dZiuoxukUTdGrZMdK0XUkN80VQ17oW12GYc5bqK5DW2d8LL8g
JlqS11LOz95pd7P6zE04pxF/AX70hVA=
"""
)

# file python-config
PYTHON_CONFIG = convert(
    """
eJyNVV1P2zAUfc+v8ODBiSABxlulTipbO6p1LWqBgVhlhcZpPYUkctzSivHfd6+dpGloGH2Ja/ue
e+65Hz78xNhtf3x90xmw7vCWsRPGLvpDNuz87MKfdKMWSWxZ4ilNpCLZJiuWc66SVFUOZkkcirll
rfxIBAzOMtImDzSVPBRrekwoX/OZu/0r4lm0DHiG60g86u8sjPw5rCyy86NRkB8QuuBRSqfAKESn
3orLTCQxE3GYkC9tYp8fk89OSwNsmXgizrhUtnumeSgeo5GbLUMk49Rv+2nK48Cm/qMwfp333J2/
dVcAGE0CIQHBsgIeEr4Wij0LtWDLzJ9ze5YEvH2WI6CHTAVcSu9ZCsXtgxu81CIvp6/k4eXsdfo7
PvDCRD75yi41QitfzlcPp1OI7i/1/iQitqnr0iMgQ+A6wa+IKwwdxyk9IiXNAzgquTFU8NIxAVjM
osm1Zz526e+shQ4hKRVci69nPC3Kw4NQEmkQ65E7OodxorSvxjvpBjQHDmWFIQ1mlmzlS5vedseT
/mgIEsMJ7Lxz2bLAF9M5xeLEhdbHxpWOw0GdkJApMVBRF1y+a0z3c9WZPAXGFcFrJgCIB+024uad
0CrzmEoRa3Ub4swNIHPGf7QDV+2uj2OiFWsChgCwjKqN6rp5izpbH6Wc1O1TclQTP/XVwi6anTr1
1sbubjZLI1+VptPSdCfwnFBrB1jvebrTA9uUhU2/9gad7xPqeFkaQcnnLbCViZK8d7R1kxzFrIJV
8EaLYmKYpvGVkig+3C5HCXbM1jGCGekiM2pRCVPyRyXYdPf6kcbWEQ36F5V4Gq9N7icNNw+JHwRE
LTgxRXACpvnQv/PuT0xCCAywY/K4hE6Now2qDwaSE5FB+1agsoUveYDepS83qFcF1NufvULD3fTl
g6Hgf7WBt6lzMeiyyWVn3P1WVbwaczHmTzE9A5SyItTVgFYyvs/L/fXlaNgbw8v3azT+0eikVlWD
/vBHbzQumP23uBCjsYdrL9OWARwxs/nuLOzeXbPJTa/Xv6sUmQir5pC1YRLz3eA+CD8Z0XpcW8v9
MZWF36ryyXXf3yBIz6nzqz8Muyz0m5Qj7OexfYo/Ph3LqvkHUg7AuA==
"""
)

MH_MAGIC = 0xFEEDFACE
MH_CIGAM = 0xCEFAEDFE
MH_MAGIC_64 = 0xFEEDFACF
MH_CIGAM_64 = 0xCFFAEDFE
FAT_MAGIC = 0xCAFEBABE
BIG_ENDIAN = ">"
LITTLE_ENDIAN = "<"
LC_LOAD_DYLIB = 0xC
maxint = majver == 3 and getattr(sys, "maxsize") or getattr(sys, "maxint")


class fileview(object):
    """
    A proxy for file-like objects that exposes a given view of a file.
    Modified from macholib.
    """

    def __init__(self, fileobj, start=0, size=maxint):
        if isinstance(fileobj, fileview):
            self._fileobj = fileobj._fileobj
        else:
            self._fileobj = fileobj
        self._start = start
        self._end = start + size
        self._pos = 0

    def __repr__(self):
        return "<fileview [%d, %d] %r>" % (self._start, self._end, self._fileobj)

    def tell(self):
        return self._pos

    def _checkwindow(self, seekto, op):
        if not (self._start <= seekto <= self._end):
            raise IOError("%s to offset %d is outside window [%d, %d]" % (op, seekto, self._start, self._end))

    def seek(self, offset, whence=0):
        seekto = offset
        if whence == os.SEEK_SET:
            seekto += self._start
        elif whence == os.SEEK_CUR:
            seekto += self._start + self._pos
        elif whence == os.SEEK_END:
            seekto += self._end
        else:
            raise IOError("Invalid whence argument to seek: {!r}".format(whence))
        self._checkwindow(seekto, "seek")
        self._fileobj.seek(seekto)
        self._pos = seekto - self._start

    def write(self, bytes):
        here = self._start + self._pos
        self._checkwindow(here, "write")
        self._checkwindow(here + len(bytes), "write")
        self._fileobj.seek(here, os.SEEK_SET)
        self._fileobj.write(bytes)
        self._pos += len(bytes)

    def read(self, size=maxint):
        assert size >= 0
        here = self._start + self._pos
        self._checkwindow(here, "read")
        size = min(size, self._end - here)
        self._fileobj.seek(here, os.SEEK_SET)
        bytes = self._fileobj.read(size)
        self._pos += len(bytes)
        return bytes


def read_data(file, endian, num=1):
    """
    Read a given number of 32-bits unsigned integers from the given file
    with the given endianness.
    """
    res = struct.unpack(endian + "L" * num, file.read(num * 4))
    if len(res) == 1:
        return res[0]
    return res


def mach_o_change(path, what, value):
    """
    Replace a given name (what) in any LC_LOAD_DYLIB command found in
    the given binary with a new name (value), provided it's shorter.
    """

    def do_macho(file, bits, endian):
        # Read Mach-O header (the magic number is assumed read by the caller)
        cputype, cpusubtype, filetype, ncmds, sizeofcmds, flags = read_data(file, endian, 6)
        # 64-bits header has one more field.
        if bits == 64:
            read_data(file, endian)
        # The header is followed by ncmds commands
        for _ in range(ncmds):
            where = file.tell()
            # Read command header
            cmd, cmdsize = read_data(file, endian, 2)
            if cmd == LC_LOAD_DYLIB:
                # The first data field in LC_LOAD_DYLIB commands is the
                # offset of the name, starting from the beginning of the
                # command.
                name_offset = read_data(file, endian)
                file.seek(where + name_offset, os.SEEK_SET)
                # Read the NUL terminated string
                load = file.read(cmdsize - name_offset).decode()
                load = load[: load.index("\0")]
                # If the string is what is being replaced, overwrite it.
                if load == what:
                    file.seek(where + name_offset, os.SEEK_SET)
                    file.write(value.encode() + "\0".encode())
            # Seek to the next command
            file.seek(where + cmdsize, os.SEEK_SET)

    def do_file(file, offset=0, size=maxint):
        file = fileview(file, offset, size)
        # Read magic number
        magic = read_data(file, BIG_ENDIAN)
        if magic == FAT_MAGIC:
            # Fat binaries contain nfat_arch Mach-O binaries
            nfat_arch = read_data(file, BIG_ENDIAN)
            for _ in range(nfat_arch):
                # Read arch header
                cputype, cpusubtype, offset, size, align = read_data(file, BIG_ENDIAN, 5)
                do_file(file, offset, size)
        elif magic == MH_MAGIC:
            do_macho(file, 32, BIG_ENDIAN)
        elif magic == MH_CIGAM:
            do_macho(file, 32, LITTLE_ENDIAN)
        elif magic == MH_MAGIC_64:
            do_macho(file, 64, BIG_ENDIAN)
        elif magic == MH_CIGAM_64:
            do_macho(file, 64, LITTLE_ENDIAN)

    assert len(what) >= len(value)

    with open(path, "r+b") as f:
        do_file(f)


if __name__ == "__main__":
    main()

# TODO:
# Copy python.exe.manifest
# Monkeypatch distutils.sysconfig
