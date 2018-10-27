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
                    print("\n", end="")
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
                print("...%s%s" % (self.in_progress, msg))
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
    pythonpath = os.pathsep.join(wheels)

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
                args += ["--cert", cert_file.name]
            args += sys.argv[1:]

            sys.exit(_main(args))
        finally:
            if cert_file is not None:
                os.remove(cert_file.name)
    """
    ).encode("utf8")

    cmd = [py_executable, "-"] + project_names
    logger.start_progress("Installing %s..." % (", ".join(project_names)))
    logger.indent += 2

    env = {
        "PYTHONPATH": pythonpath,
        "JYTHONPATH": pythonpath,  # for Jython < 3.x
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


def path_locations(home_dir):
    """Return the path locations for the environment (where libraries are,
    where scripts go, etc)"""
    home_dir = os.path.abspath(home_dir)
    # XXX: We'd use distutils.sysconfig.get_python_inc/lib but its
    # prefix arg is broken: http://bugs.python.org/issue3386
    if is_win:
        # Windows has lots of problems with executables with spaces in
        # the name; this function will remove them (using the ~1
        # format):
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
        copyfile("lib", lib64_link)


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
3WFNNa14+S9FG+TYTrVfYA1F8L80iX54
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
eJyFVVFv2zYQftevuMoOnBS1gr0WGIZ08RADSRw4boBhGGhGOsUcKFIjKbUu9uN7lC2JsrXWDzZM
fnf38e6+uwlsdsJCLiRCUVkHrwiVxYy+hHqDbQKvQl3z1ImaO0xyYXdbeP9FuJ1QwMFUSnmcP4dL
2DlXfry+9v/sDqVMUl3AFVi0Vmj1PokmcKtBaecNQTjIhMHUyX0SRXmlKIpWkGEbDuYZzBZfCVcL
4youUdVQ6AyBqwwMusoocBrcDsmpKbgEQgijVYHKJbMI6DMhoEUHWmbhLdTcCP4q0TYokYNDev5c
QTxlq/tb9rJcbz7f3LOnm81d3GD8x3uav30FfwrnwCEOYRyAKot+FvXPzd3q8W71sBiJ3d2dMugu
fsxjCPsBmz+Wz3fsab16eNqw1ctivV7eBnwm8EzeuQIsSrcHqVMqwHbqq8/aarKSO+oYKhKXUn9p
SmWw0DVBdQ7bBlwaTR62bc+1tpaYb5PhUyScu48CRgvDLQbtMrMnMQ6dY5022JDRRrwJxWUfJwwP
ge0YIAVGfcUC1M8s8MxitFZjmR9W64hui7p4fBlWMZ5y81b/9cvfMbz7FWZKq4yOTeW1hbNBEWU+
b+/ejXMu95lOx696uXb8Go4T+Kw8R2EMSqx5KLkkCkQ+ZBZFbZsHL4OYseAvY3EPO5MYTBuhDZQa
TwPza8Y+LR/Z483Dgjwd4R3f7bTXx9Znkw6T6PAL83/hRD3jNAKFjuEx9NJkq5t+fabLvdvRwbw4
nEFTzwO6U+q34cvY7fL55tP94tg58XEA/q7LfdPsaUXFoEIMJdHF5iSW0+48CnDQ82G7n3XzAD6q
Bmo5XuOA0NQ67ir7AXJtQhtLKO7XhC0l39PGOBsHPvzBuHUSjoOnA0ldozGC9gZ5rek3+y3ALHO/
kT7AP379lQZLSnFDLtwWihfYxw4nZd+ZR7myfkI2ZTRCuRxmF/bCzkbhcElvYamW9PbDGrvqPKC0
+D/uLi/sFcxGjOHylYagZzzsjjhw206RQwrWIwOxS2dnk+40xOjX8bTPegz/gdWVSXuaowNuOLda
wYyNuRPSTcd/B48Ppeg=
"""
)

# file activate.csh
ACTIVATE_CSH = convert(
    """
eJx1U2FP2zAQ/e5f8TAV3Soo+0zXbYUiDQkKQgVp2ibjJNfFUuIg22nVf885SVFLO3+I7Lt3fr6X
d8eY58ZjYQpCWfuAhFB7yrAyIYf0Ve1SQmLsuU6DWepAw9TnEoOFq0rwdjAUx/hV1Ui1tVWAqy1M
QGYcpaFYx+yVI67LkKwx1UuTEaYGl4X2Bl+zJpAlP/6V2hTDtCq/DYXQhdEeGW040Q/Eb+t9V/e3
U/V88zh/mtyqh8n8J47G+IKTE3gKZJdoYrK3h5MRU1tGYS83gqNc+3yEgyyP93cP820evHLvr2H8
kaYB/peoyY7aVHzpJnE9e+6I5Z+ji4GMTNJWNuOQq6MA1N25p8pW9HWdVWlfsNpPDbdxjgpaahuw
1M7opCA/FFu1uwxC7L8KUqmto1KyQe3rx0I0Eovdf7BVe67U5c1MzSZ310pddGheZoFPWyytRkzU
aCA/I+RkBXhFXr5aWV0SxjhUI6jwdAj8kmhPzX7nTfJFkM3MImp2VdVFFq1vLHSU5szYQK4Ri+Jd
xlW2JBtOGcyYVW7SnB3v6RS91g3gKapZ0oWxbHVteYIIq3iv7QeuSrUj6KSqQ+yqsxDj1ivNQxKF
YON10Q+NH/ARS95i5Tuqq2Vxfvc23f/FO6zrtXXmJr+ZtMY9/A15ZXFWtmch2rEQbxoCUb0=
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
rKQDxR6N/rffXv+lROXet/9Q+l9I4D1U
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
