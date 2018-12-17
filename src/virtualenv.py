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

__version__ = "16.1.0"
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
        except IOError:
            cert_data = None

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
    import warnings

    with warnings.catch_warnings():
        # Ignore deprecation of the imp module
        # TODO: do not use deprecated imp module
        warnings.simplefilter("ignore")
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
    # normalize paths using realpath to ensure that a virtualenv correctly identifies itself even
    # when adressed over a symlink
    proc_stdout = os.path.normcase(os.path.realpath(proc_stdout))
    norm_home_dir = os.path.normcase(os.path.realpath(home_dir))
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

    if sys.version_info >= (3, 4):
        # Add xonsh support
        files["activate.xsh"] = ACTIVATE_XSH

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
        os.symlink("lib", lib64_link)
    else:
        copyfile(lib_dir, lib64_link, symlink=False)


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
    "activate.xsh",
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
k0qE
"""
)

# file activate.sh
ACTIVATE_SH = convert(
    """
eJytVV1v2kAQfPevWAxKk7QU0cdWRCUKEkgJRJhStU3lHPYSn2rO6O5MQj7+e/dsY2wc6EPDA2Dv
3N3szuxeHSYBVzDnIcIiVhpmCLFCH+65DsBWUSw9hBkXLeZpvmIabTidy2gBM6aCU6sO6ygGjwkR
aZCxAK7B5xI9Ha4ty8fNKjg+gScL6BMLhRqac1iu/ciDs5aPq5aIwxA+nR21rQRTB4kGFYU+oFhx
GYkFCg0rJjmbhagyVA1+QfMRGk/T7vi9+wK/aZ2OpVCgZYzA50ABoPx89EImKS2mgYVhspyi2Xq7
8eSOLi/c6WA8+da9dK+7kz5tZ9N+X0AHKBK8+ZhIx25U0HaOwIdlJHUCzN+lKVcWJfE5/xeZH5P+
aNgfXfX2UMrjFWJ5pEovDx0kWUYR1azuiWdUEMWkj4+a1E7sAEz48KiCD3AfcC+AgK0QGP1QyIsW
CxPWAUlgnJZtRX7zSBGSRkdwRwzIQPRvHknzsGRkyWyp+gjwnVwZxToLay7usm1KQFMgaJgSgxcw
cYcK7snezDdfazBWpWPJYktijv5GACq/MOU/7zr9ZlLq5+f85U+n7057Y2cwGjZfkyFJsinJxLmh
S0U7ILDT3qOs065I6rSrWjrtgyJm4Q2RFLKJ9obTbfo1w61t0uuALSLho6I+Mh2MO/Tq4GA4hw2g
tkOgaUKb1t+c/mLRtEjjXEoMccVKLV0YFuWzLavAtmO7buHRdW0rq0MxJavSbFTJtFGzhwK65brn
g6E77F71XPdzBiv2cc572xCmYPTGKsl6qFX3NJahtdOmu0dZRrnUnskpxewvBk73/LLnXo9HV9eT
ijF3jdAxJB2j8FZ0+2Fb0HQbqinUOvCwx5FVeGlTDBWWFxzf0nBAwRYIN6XC39i3J1BanE3DgrNN
8nW4Yn8QVCzRzIZYsJAzlV0glATX7xSNdYnMXxvCEq0iotCSxevm6GhnJ+p2c21YVvqY31jLNQ0d
Ac1FhrMbX+3UzW8yB99gBv7n/Puf2ffa3CPN/gKu/HeT
"""
)

# file activate.fish
ACTIVATE_FISH = convert(
    """
eJyFVm1v2zYQ/q5fcZUdyClqB93HAMOQNh5iIIkDxw0wbAPNSJTFQSI1klLrYj9+R8qSKFtp8yGG
yOfe77njBLYZ15DynEFRaQOvDCrNEvzHxR52WlYqZvDKxRWNDa+pYYuU62wH779yk3EBFFQlhAXb
c5hBZkx5fXVlv3TG8nwRywIuQTOtuRTvF8EEbiUIaawgcAMJVyw2+WERBGkl0IoUQF6pznh6ICU1
GcwTCD9LUTNlNBp0htyFkaBlwawje7AiEFMBqE7uBf/OwgDwTzPjRI7KplTt6+7CCrUXPejPj387
RCqVM4SHygBG62N+WSzmR9yItnDaf1xPOyWNS0wkzW+cSfCAgb3wsmCtvZUFF+55FlxyRrLQmLKx
w39gFETXEUR/iejEZMLaOlt70fIbFqjmylQ0Z6KGQiYMqEhQu6mUsKZNxrCaqqA5hoVQKQomzCJy
VicItImReeLfQk0Vp6850w7FUzAMm28uMG1kfX9LXlab7Zebe/J0s70LByme77+BPYXZMDvncpdD
OQZniK4WP/Pij+3d+vFu/bAc8aW7O3Whu/ixH0PYD7z5ffV8R54264enLVm/LDeb1a3nzwSeUTvW
nRWlOUAuYyzIzvUraavrMrWzRaN5Lr+60ilWyBqhMoWdA5dKooZdOwFaWY2e7xbDUHI4Vx94Hi0V
1cxrn0if2Gg6SRupmHNGKr7ngua9Hd88eLJjgBgI9hnxUD+TYGcSo7Uay/ywWkd0W9Tl48uwiqFj
Ho6VEN79CpGQIsFjVVmusWhQxDydt3fvxn0uD4mMx696+r4Rrj9X34D4tOqidJFO4IuwkXKlWM5q
6hN5EXijYxhfELRk8fIDISHeJyFhDzsjKpJ9sBCmDb8H8yCceuquCPm0eiSPNw9L1Nzge/930551
O1sjPFwEzS/M/4UTTo675fF+DM98LcMZ29evPJgMD+ZFc3bcTQ7d8f/7MDJyu3q++XS/PPZjeByz
n2V5cBSKKywOFmZItM42RQqe9vyR1gMm+SQ648gAPsoxbGRas4FDU22oqfQHt1Q9GY0oal8Buszp
AR8EZ0PGmm+EWyX+kHlqnJS4FxXH7YRaa/xNfvMwq9Q+OD7AP/aJUypWYoqdc/5OErRgvW1//vad
ehwCpJ+7royKC5NCdKEvdDQKhxnGQmKZY+zNsuy3E8s1e0Pd7EJfQjQiDDPkA7MeD7sj9NS2s6lJ
wWZkzHbp7GTsIyFkdulP+6yH+GJoHoIdcHRsDqdhS5ix4XnitOv4/wFb3Ubb
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

# file activate.xsh
ACTIVATE_XSH = convert(
    """
eJyFU11rwjAUfc+vuIt9sMz1Bwg+OCYoaB2bkw2RkNlbLdSkJLFsjP33JdV+aN2Wh5L7eW7PuaGU
vkqhd8A3Jsm5QdAblWQGYqkgT5Q58BRFTiklsZJ7+HDJgZEy1ZDsM6kMbNEwjRlwDex0JyTCGFiE
ZdcuV1vt9wnYk8RAs89IbigkAniacI36GHInwrR0rk55a1IWel9BEHwHFqZL2Xz6wJaTp8XLcMoe
h4sx7QGlft3Jc04YgNfKPAO7Ev4f7m0xnofj+WzUBq1Cbegq9NcAdVJFVxkbhcuCtONc55x5jaS6
UkgRoTbq4IRACkKagnUrR13egWdMYygTb65rUavpBCEdOAiNtptSmGLOhYGcq4S/p6hJU/rV5RBr
n1xtavlq1BHS/CMbU5SxhocxalNa2jnSCw29prXqr4+OgEdR96zxbbW1Xd8aFuR+ErJwOBtZhB7Y
rRdmsFAH7IHCLOUbLCyfkIsFub4TJU2NtbB11lNEf5O+mPt8WwqNm8tx+UhsjbubnRRugLu9+5YP
6AcvDiI9
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
