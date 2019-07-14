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

import ast
import base64
import codecs
import contextlib
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
import tempfile
import textwrap
import zipfile
import zlib
from distutils.util import strtobool
from os.path import join

try:
    import ConfigParser
except ImportError:
    # noinspection PyPep8Naming
    import configparser as ConfigParser

__version__ = "16.6.2"
virtualenv_version = __version__  # legacy
DEBUG = os.environ.get("_VIRTUALENV_DEBUG", None) == "1"
if sys.version_info < (2, 7):
    print("ERROR: {}".format(sys.exc_info()[1]))
    print("ERROR: this script requires Python 2.7 or greater.")
    sys.exit(101)

HERE = os.path.dirname(os.path.abspath(__file__))
IS_ZIPAPP = os.path.isfile(HERE)

try:
    # noinspection PyUnresolvedReferences,PyUnboundLocalVariable
    basestring
except NameError:
    basestring = str

PY_VERSION = "python{}.{}".format(sys.version_info[0], sys.version_info[1])

IS_PYPY = hasattr(sys, "pypy_version_info")
IS_WIN = sys.platform == "win32"
IS_CYGWIN = sys.platform == "cygwin"
IS_DARWIN = sys.platform == "darwin"
ABI_FLAGS = getattr(sys, "abiflags", "")

USER_DIR = os.path.expanduser("~")
if IS_WIN:
    DEFAULT_STORAGE_DIR = os.path.join(USER_DIR, "virtualenv")
else:
    DEFAULT_STORAGE_DIR = os.path.join(USER_DIR, ".virtualenv")
DEFAULT_CONFIG_FILE = os.path.join(DEFAULT_STORAGE_DIR, "virtualenv.ini")

if IS_PYPY:
    EXPECTED_EXE = "pypy"
else:
    EXPECTED_EXE = "python"

# Return a mapping of version -> Python executable
# Only provided for Windows, where the information in the registry is used
if not IS_WIN:

    def get_installed_pythons():
        return {}


else:
    try:
        import winreg
    except ImportError:
        # noinspection PyUnresolvedReferences
        import _winreg as winreg

    def get_installed_pythons():
        final_exes = dict()

        # Grab exes from 32-bit registry view
        exes = _get_installed_pythons_for_view("-32", winreg.KEY_WOW64_32KEY)
        # Grab exes from 64-bit registry view
        exes_64 = _get_installed_pythons_for_view("-64", winreg.KEY_WOW64_64KEY)
        # Check if exes are unique
        if set(exes.values()) != set(exes_64.values()):
            exes.update(exes_64)

        # Create dict with all versions found
        for version, bitness in sorted(exes):
            exe = exes[(version, bitness)]
            # Add minor version (X.Y-32 or X.Y-64)
            final_exes[version + bitness] = exe
            # Add minor extensionless version (X.Y); 3.2-64 wins over 3.2-32
            final_exes[version] = exe
            # Add major version (X-32 or X-64)
            final_exes[version[0] + bitness] = exe
            # Add major extensionless version (X); 3.3-32 wins over 3.2-64
            final_exes[version[0]] = exe

        return final_exes

    def _get_installed_pythons_for_view(bitness, view):
        exes = dict()
        # If both system and current user installations are found for a
        # particular Python version, the current user one is used
        for key in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
            try:
                python_core = winreg.OpenKey(key, "Software\\Python\\PythonCore", 0, view | winreg.KEY_READ)
            except WindowsError:
                # No registered Python installations
                continue
            i = 0
            while True:
                try:
                    version = winreg.EnumKey(python_core, i)
                    i += 1
                    try:
                        at_path = winreg.QueryValue(python_core, "{}\\InstallPath".format(version))
                    except WindowsError:
                        continue
                    # Remove bitness from version
                    if version.endswith(bitness):
                        version = version[: -len(bitness)]
                    exes[(version, bitness)] = join(at_path, "python.exe")
                except WindowsError:
                    break
            winreg.CloseKey(python_core)

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

MAJOR, MINOR = sys.version_info[:2]
if MAJOR == 2:
    if MINOR >= 6:
        REQUIRED_MODULES.extend(["warnings", "linecache", "_abcoll", "abc"])
    if MINOR >= 7:
        REQUIRED_MODULES.extend(["_weakrefset"])
elif MAJOR == 3:
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
    if MINOR >= 2:
        REQUIRED_FILES[-1] = "config-{}".format(MAJOR)
    if MINOR >= 3:
        import sysconfig

        platform_dir = sysconfig.get_config_var("PLATDIR")
        REQUIRED_FILES.append(platform_dir)
        REQUIRED_MODULES.extend(["base64", "_dummy_thread", "hashlib", "hmac", "imp", "importlib", "rlcompleter"])
    if MINOR >= 4:
        REQUIRED_MODULES.extend(["operator", "_collections_abc", "_bootlocale"])
    if MINOR >= 6:
        REQUIRED_MODULES.extend(["enum"])

if IS_PYPY:
    # these are needed to correctly display the exceptions that may happen
    # during the bootstrap
    REQUIRED_MODULES.extend(["traceback", "linecache"])

    if MAJOR == 3:
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

    @staticmethod
    def level_matches(level, consumer_level):
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


def mkdir(at_path):
    if not os.path.exists(at_path):
        logger.info("Creating %s", at_path)
        os.makedirs(at_path)
    else:
        logger.info("Directory %s already exists", at_path)


def copy_file_or_folder(src, dest, symlink=True):
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
    if symlink and hasattr(os, "symlink") and not IS_WIN:
        logger.info("Symlinking %s", dest)
        try:
            os.symlink(os.path.realpath(src), dest)
        except (OSError, NotImplementedError):
            logger.info("Symlinking failed, copying to %s", dest)
            copy_file_or_folder(src, dest, symlink)
    else:
        logger.info("Copying to %s", dest)
        copy_file_or_folder(src, dest, symlink)


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


def rm_tree(folder):
    if os.path.exists(folder):
        logger.notify("Deleting tree %s", folder)
        shutil.rmtree(folder)
    else:
        logger.info("Do not need to delete %s; already gone", folder)


def make_exe(fn):
    if hasattr(os, "chmod"):
        old_mode = os.stat(fn).st_mode & 0xFFF  # 0o7777
        new_mode = (old_mode | 0x16D) & 0xFFF  # 0o555, 0o7777
        os.chmod(fn, new_mode)
        logger.info("Changed mode of %s to %s", fn, oct(new_mode))


def _find_file(filename, folders):
    for folder in reversed(folders):
        files = glob.glob(os.path.join(folder, filename))
        if files and os.path.isfile(files[0]):
            return True, files[0]
    return False, filename


@contextlib.contextmanager
def virtualenv_support_dirs():
    """Context manager yielding either [virtualenv_support_dir] or []"""

    # normal filesystem installation
    if os.path.isdir(join(HERE, "virtualenv_support")):
        yield [join(HERE, "virtualenv_support")]
    elif IS_ZIPAPP:
        tmpdir = tempfile.mkdtemp()
        try:
            with zipfile.ZipFile(HERE) as zipf:
                for member in zipf.namelist():
                    if os.path.dirname(member) == "virtualenv_support":
                        zipf.extract(member, tmpdir)
            yield [join(tmpdir, "virtualenv_support")]
        finally:
            shutil.rmtree(tmpdir)
    # probably a bootstrap script
    elif os.path.splitext(os.path.dirname(__file__))[0] != "virtualenv":
        try:
            # noinspection PyUnresolvedReferences
            import virtualenv
        except ImportError:
            yield []
        else:
            yield [join(os.path.dirname(virtualenv.__file__), "virtualenv_support")]
    # we tried!
    else:
        yield []


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

    @staticmethod
    def get_config_files():
        config_file = os.environ.get("VIRTUALENV_CONFIG_FILE", False)
        if config_file and os.path.exists(config_file):
            return [config_file]
        return [DEFAULT_CONFIG_FILE]

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
                key = "--{}".format(key)  # only prefer long opts
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
                    print("An error occurred during configuration: {!r}".format(e))
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
        Overriding to make updating the defaults after instantiation of
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

    parser.add_option(
        "-v", "--verbose", action="count", dest="verbose", default=5 if DEBUG else 0, help="Increase verbosity."
    )

    parser.add_option("-q", "--quiet", action="count", dest="quiet", default=0, help="Decrease verbosity.")

    parser.add_option(
        "-p",
        "--python",
        dest="python",
        metavar="PYTHON_EXE",
        help="The Python interpreter to use, e.g., --python=python3.5 will use the python3.5 "
        "interpreter to create the new environment.  The default is the interpreter that "
        "virtualenv was installed with ({})".format(sys.executable),
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

    parser.add_option(
        "--extra-search-dir",
        dest="search_dirs",
        action="append",
        metavar="DIR",
        default=[],
        help="Directory to look for setuptools/pip distributions in. " "This option can be used multiple times.",
    )

    parser.add_option(
        "--download",
        dest="download",
        default=True,
        action="store_true",
        help="Download pre-installed packages from PyPI.",
    )

    parser.add_option(
        "--no-download",
        "--never-download",
        dest="download",
        action="store_false",
        help="Do not download pre-installed packages from PyPI.",
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
        # noinspection PyUnresolvedReferences
        extend_parser(parser)  # noqa: F821

    options, args = parser.parse_args()

    global logger

    if "adjust_options" in globals():
        # noinspection PyUnresolvedReferences
        adjust_options(options, args)  # noqa: F821

    verbosity = options.verbose - options.quiet
    logger = Logger([(Logger.level_for_integer(2 - verbosity), sys.stdout)])

    def should_reinvoke(options):
        """Do we need to reinvoke ourself?"""
        # Did the user specify the --python option?
        if options.python and not os.environ.get("VIRTUALENV_INTERPRETER_RUNNING"):
            interpreter = resolve_interpreter(options.python)
            if interpreter != sys.executable:
                # The user specified a different interpreter, so we have to reinvoke.
                return interpreter

        # At this point, we know the user wants to use sys.executable to create the
        # virtual environment. But on Windows, sys.executable may be a venv redirector,
        # in which case we still need to locate the underlying actual interpreter, and
        # reinvoke using that.
        if IS_WIN:
            # OK. Now things get really fun...
            #
            # If we are running from a venv, with a redirector, then what happens is as
            # follows:
            #
            #   1. The redirector sets __PYVENV_LAUNCHER__ in the environment to point
            #      to the redirector executable.
            #   2. The redirector launches the "base" Python (from the home value in
            #      pyvenv.cfg).
            #   3. The base Python executable sees __PYVENV_LAUNCHER__ in the environment
            #      and sets sys.executable to that value.
            #   4. If site.py gets run, it sees __PYVENV_LAUNCHER__, and sets
            #      sys._base_executable to _winapi.GetModuleFileName(0) and removes
            #      __PYVENV_LAUNCHER__.
            #
            # Unfortunately, that final step (site.py) may not happen. There are 2 key
            # times when that is the case:
            #
            #   1. Python 3.7.2, which had the redirector but not the site.py code.
            #   2. Running a venv from a virtualenv, which uses virtualenv's custom
            #      site.py.
            #
            # So, we check for sys._base_executable, but if it's not present and yet we
            # have __PYVENV_LAUNCHER__, we do what site.py would have done and get our
            # interpreter from GetModuleFileName(0). We also remove __PYVENV_LAUNCHER__
            # from the environment, to avoid loops (actually, mainly because site.py
            # does so, and my head hurts enough buy now that I just want to be safe!)

            # In Python 3.7.4, the rules changed so that sys._base_executable is always
            # set. So we now only return sys._base_executable if it's set *and does not
            # match sys.executable* (we still have to check that it's set, as we need to
            # support Python 3.7.3 and earlier).

            # Phew.

            if getattr(sys, "_base_executable", sys.executable) != sys.executable:
                return sys._base_executable

            if "__PYVENV_LAUNCHER__" in os.environ:
                import _winapi

                del os.environ["__PYVENV_LAUNCHER__"]
                return _winapi.GetModuleFileName(0)

        # We don't need to reinvoke
        return None

    interpreter = should_reinvoke(options)
    if interpreter is None:
        # We don't need to reinvoke - if the user asked us to, tell them why we
        # aren't.
        if options.python:
            logger.warn("Already using interpreter {}".format(sys.executable))
    else:
        env = os.environ.copy()
        logger.notify("Running virtualenv with interpreter {}".format(interpreter))
        env["VIRTUALENV_INTERPRETER_RUNNING"] = "true"
        # Remove the variable __PYVENV_LAUNCHER__ if it's present, as it causes the
        # interpreter to redirect back to the virtual environment.
        if "__PYVENV_LAUNCHER__" in env:
            del env["__PYVENV_LAUNCHER__"]
        file = __file__
        if file.endswith(".pyc"):
            file = file[:-1]
        elif IS_ZIPAPP:
            file = HERE
        sub_process_call = subprocess.Popen([interpreter, file] + sys.argv[1:], env=env)
        raise SystemExit(sub_process_call.wait())

    if not args:
        print("You must provide a DEST_DIR")
        parser.print_help()
        sys.exit(2)
    if len(args) > 1:
        print("There must be only one argument: DEST_DIR (you gave {})".format(" ".join(args)))
        parser.print_help()
        sys.exit(2)

    home_dir = args[0]

    if os.path.exists(home_dir) and os.path.isfile(home_dir):
        logger.fatal("ERROR: File already exists and is not a directory.")
        logger.fatal("Please provide a different path or delete the file.")
        sys.exit(3)

    if os.pathsep in home_dir:
        logger.fatal("ERROR: target path contains the operating system path separator '{}'".format(os.pathsep))
        logger.fatal("This is not allowed as would make the activation scripts unusable.".format(os.pathsep))
        sys.exit(3)

    if os.environ.get("WORKING_ENV"):
        logger.fatal("ERROR: you cannot run virtualenv while in a working env")
        logger.fatal("Please deactivate your working env, then re-run this script")
        sys.exit(3)

    if "PYTHONHOME" in os.environ:
        logger.warn("PYTHONHOME is set.  You *must* activate the virtualenv before using it")
        del os.environ["PYTHONHOME"]

    if options.relocatable:
        make_environment_relocatable(home_dir)
        return

    with virtualenv_support_dirs() as search_dirs:
        create_environment(
            home_dir,
            site_packages=options.system_site_packages,
            clear=options.clear,
            prompt=options.prompt,
            search_dirs=search_dirs + options.search_dirs,
            download=options.download,
            no_setuptools=options.no_setuptools,
            no_pip=options.no_pip,
            no_wheel=options.no_wheel,
            symlink=options.symlink,
        )
    if "after_install" in globals():
        # noinspection PyUnresolvedReferences
        after_install(options, home_dir)  # noqa: F821


def call_subprocess(
    cmd,
    show_stdout=True,
    filter_stdout=None,
    cwd=None,
    raise_on_return_code=True,
    extra_env=None,
    remove_from_env=None,
    stdin=None,
):
    cmd_parts = []
    for part in cmd:
        if len(part) > 45:
            part = part[:20] + "..." + part[-20:]
        if " " in part or "\n" in part or '"' in part or "'" in part:
            part = '"{}"'.format(part.replace('"', '\\"'))
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
    logger.debug("Running command {}".format(cmd_desc))
    if extra_env or remove_from_env:
        env = os.environ.copy()
        if extra_env:
            env.update(extra_env)
        if remove_from_env:
            for var_name in remove_from_env:
                env.pop(var_name, None)
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
            with proc.stdin:
                proc.stdin.write(stdin)

        encoding = sys.getdefaultencoding()
        fs_encoding = sys.getfilesystemencoding()
        with proc.stdout as stdout:
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
        if raise_on_return_code:
            if all_output:
                logger.notify("Complete output from command {}:".format(cmd_desc))
                logger.notify("\n".join(all_output) + "\n----------------------------------------")
            raise OSError("Command {} failed with error code {}".format(cmd_desc, proc.returncode))
        else:
            logger.warn("Command {} had error code {}".format(cmd_desc, proc.returncode))
    return all_output


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
        search_dirs_context = virtualenv_support_dirs
    else:

        @contextlib.contextmanager
        def search_dirs_context():
            yield search_dirs

    with search_dirs_context() as search_dirs:
        _install_wheel_with_search_dir(download, project_names, py_executable, search_dirs)


def _install_wheel_with_search_dir(download, project_names, py_executable, search_dirs):
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

    find_links = " ".join(space_path2url(d) for d in search_dirs)

    extra_args = ["--ignore-installed"]
    if DEBUG:
        extra_args.append("-v")

    config = _pip_config(py_executable, python_path)
    defined_cert = bool(config.get("install.cert") or config.get(":env:.cert") or config.get("global.cert"))

    script = textwrap.dedent(
        """
        import sys
        import pkgutil
        import tempfile
        import os

        defined_cert = {defined_cert}

        try:
            from pip._internal import main as _main
            cert_data = pkgutil.get_data("pip._vendor.certifi", "cacert.pem")
        except ImportError:
            from pip import main as _main
            cert_data = pkgutil.get_data("pip._vendor.requests", "cacert.pem")
        except IOError:
            cert_data = None

        if not defined_cert and cert_data is not None:
            cert_file = tempfile.NamedTemporaryFile(delete=False)
            cert_file.write(cert_data)
            cert_file.close()
        else:
            cert_file = None

        try:
            args = ["install"] + [{extra_args}]
            if cert_file is not None:
                args += ["--cert", cert_file.name]
            args += sys.argv[1:]

            sys.exit(_main(args))
        finally:
            if cert_file is not None:
                os.remove(cert_file.name)
    """.format(
            defined_cert=defined_cert, extra_args=", ".join(repr(i) for i in extra_args)
        )
    ).encode("utf8")

    cmd = [py_executable, "-"] + project_names
    logger.start_progress("Installing {}...".format(", ".join(project_names)))
    logger.indent += 2

    env = {
        "PYTHONPATH": python_path,
        "PIP_FIND_LINKS": find_links,
        "PIP_USE_WHEEL": "1",
        "PIP_ONLY_BINARY": ":all:",
        "PIP_USER": "0",
        "PIP_NO_INPUT": "1",
    }

    if not download:
        env["PIP_NO_INDEX"] = "1"

    try:
        call_subprocess(cmd, show_stdout=False, extra_env=env, stdin=script)
    finally:
        logger.indent -= 2
        logger.end_progress()


def _pip_config(py_executable, python_path):
    cmd = [py_executable, "-m", "pip", "config", "list"]
    config = {}
    for line in call_subprocess(
        cmd,
        show_stdout=False,
        extra_env={"PYTHONPATH": python_path},
        remove_from_env=["PIP_VERBOSE", "PIP_QUIET"],
        raise_on_return_code=False,
    ):
        key, _, value = line.partition("=")
        if value:
            config[key] = ast.literal_eval(value)
    return config


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
    return os.path.isfile(fpath) and is_executable(fpath)


def path_locations(home_dir, dry_run=False):
    """Return the path locations for the environment (where libraries are,
    where scripts go, etc)"""
    home_dir = os.path.abspath(home_dir)
    lib_dir, inc_dir, bin_dir = None, None, None
    # XXX: We'd use distutils.sysconfig.get_python_inc/lib but its
    # prefix arg is broken: http://bugs.python.org/issue3386
    if IS_WIN:
        # Windows has lots of problems with executables with spaces in
        # the name; this function will remove them (using the ~1
        # format):
        if not dry_run:
            mkdir(home_dir)
        if " " in home_dir:
            import ctypes

            get_short_path_name = ctypes.windll.kernel32.GetShortPathNameW
            size = max(len(home_dir) + 1, 256)
            buf = ctypes.create_unicode_buffer(size)
            try:
                # noinspection PyUnresolvedReferences
                u = unicode
            except NameError:
                u = str
            ret = get_short_path_name(u(home_dir), buf, size)
            if not ret:
                print('Error: the path "{}" has a space in it'.format(home_dir))
                print("We could not determine the short pathname for it.")
                print("Exiting.")
                sys.exit(3)
            home_dir = str(buf.value)
        lib_dir = join(home_dir, "Lib")
        inc_dir = join(home_dir, "Include")
        bin_dir = join(home_dir, "Scripts")
    elif IS_PYPY:
        lib_dir = home_dir
        inc_dir = join(home_dir, "include")
        bin_dir = join(home_dir, "bin")
    elif not IS_WIN:
        lib_dir = join(home_dir, "lib", PY_VERSION)
        inc_dir = join(home_dir, "include", PY_VERSION + ABI_FLAGS)
        bin_dir = join(home_dir, "bin")
    return home_dir, lib_dir, inc_dir, bin_dir


def change_prefix(filename, dst_prefix):
    prefixes = [sys.prefix]

    if IS_DARWIN:
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
    if IS_WIN and filename[0] in "abcdefghijklmnopqrstuvwxyz":
        filename = filename[0].upper() + filename[1:]
    for i, prefix in enumerate(prefixes):
        if IS_WIN and prefix[0] in "abcdefghijklmnopqrstuvwxyz":
            prefixes[i] = prefix[0].upper() + prefix[1:]
    for src_prefix in prefixes:
        if filename.startswith(src_prefix):
            _, relative_path = filename.split(src_prefix, 1)
            if src_prefix != os.sep:  # sys.prefix == "/"
                assert relative_path[0] == os.sep
                relative_path = relative_path[1:]
            return join(dst_prefix, relative_path)
    assert False, "Filename {} does not start with any of these prefixes: {}".format(filename, prefixes)


def find_module_filename(modname):

    if sys.version_info < (3, 4):
        # noinspection PyDeprecation
        import imp

        try:
            file_handler, filepath, _ = imp.find_module(modname)
        except ImportError:
            return None
        else:
            if file_handler is not None:
                file_handler.close()
            return filepath
    else:
        import importlib.util

        if sys.version_info < (3, 5):

            def find_spec(modname):
                # noinspection PyDeprecation
                loader = importlib.find_loader(modname)
                if loader is None:
                    return None
                else:
                    return importlib.util.spec_from_loader(modname, loader)

        else:
            find_spec = importlib.util.find_spec

        spec = find_spec(modname)
        if spec is None:
            return None
        if not os.path.exists(spec.origin):
            # https://bitbucket.org/pypy/pypy/issues/2944/origin-for-several-builtin-modules
            # on pypy3, some builtin modules have a bogus build-time file path, ignore them
            return None
        filepath = spec.origin
        # https://www.python.org/dev/peps/pep-3147/#file guarantee to be non-cached
        if os.path.basename(filepath) == "__init__.py":
            filepath = os.path.dirname(filepath)
        return filepath


def copy_required_modules(dst_prefix, symlink):
    for modname in REQUIRED_MODULES:
        if modname in sys.builtin_module_names:
            logger.info("Ignoring built-in bootstrap module: %s" % modname)
            continue
        filename = find_module_filename(modname)
        if filename is None:
            logger.info("Cannot import bootstrap module: %s" % modname)
        else:
            # special-case custom readline.so on OS X, but not for pypy:
            if (
                modname == "readline"
                and IS_DARWIN
                and not (IS_PYPY or filename.endswith(join("lib-dynload", "readline.so")))
            ):
                dst_filename = join(dst_prefix, "lib", "python{}".format(sys.version[:3]), "readline.so")
            elif modname == "readline" and IS_WIN:
                # special-case for Windows, where readline is not a standard module, though it may have been installed
                # in site-packages by a third-party package
                dst_filename = None
            else:
                dst_filename = change_prefix(filename, dst_prefix)
            if dst_filename is not None:
                copyfile(filename, dst_filename, symlink)
            if filename.endswith(".pyc"):
                py_file = filename[:-1]
                if os.path.exists(py_file):
                    copyfile(py_file, dst_filename[:-1], symlink)


def copy_required_files(src_dir, lib_dir, symlink):
    if not os.path.isdir(src_dir):
        return
    for fn in os.listdir(src_dir):
        bn = os.path.splitext(fn)[0]
        if fn != "site-packages" and bn in REQUIRED_FILES:
            copyfile(join(src_dir, fn), join(lib_dir, fn), symlink)


def copy_license(prefix, dst_prefix, lib_dir, symlink):
    """Copy the license file so `license()` builtin works"""
    lib64_dir = lib_dir.replace("lib", "lib64")
    for license_path in (
        # posix cpython
        os.path.join(prefix, os.path.relpath(lib_dir, dst_prefix), "LICENSE.txt"),
        # posix cpython installed in /usr/lib64
        os.path.join(prefix, os.path.relpath(lib64_dir, dst_prefix), "LICENSE.txt"),
        # windows cpython
        os.path.join(prefix, "LICENSE.txt"),
        # pypy
        os.path.join(prefix, "LICENSE"),
    ):
        if os.path.exists(license_path):
            dest = subst_path(license_path, prefix, dst_prefix)
            copyfile(license_path, dest, symlink)
            return
    logger.warn("No LICENSE.txt / LICENSE found in source")


def copy_include_dir(include_src, include_dest, symlink):
    """Copy headers from *include_src* to *include_dest* symlinking if required"""
    if not os.path.isdir(include_src):
        return
    # PyPy headers are located in ``pypy-dir/include`` and following code
    # avoids making ``venv-dir/include`` symlink to it
    if IS_PYPY:
        for fn in os.listdir(include_src):
            copyfile(join(include_src, fn), join(include_dest, fn), symlink)
    else:
        copyfile(include_src, include_dest, symlink)


def copy_tcltk(src, dest, symlink):
    """ copy tcl/tk libraries on Windows (issue #93) """
    for lib_version in "8.5", "8.6":
        for libname in "tcl", "tk":
            src_dir = join(src, "tcl", libname + lib_version)
            dest_dir = join(dest, "tcl", libname + lib_version)
            # Only copy the dirs from the above combinations that exist
            if os.path.exists(src_dir) and not os.path.exists(dest_dir):
                copy_file_or_folder(src_dir, dest_dir, symlink)


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
        rm_tree(lib_dir)
        # FIXME: why not delete it?
        # Maybe it should delete everything with #!/path/to/venv/python in it
        logger.notify("Not deleting %s", bin_dir)

    if hasattr(sys, "real_prefix"):
        logger.notify("Using real prefix %r", sys.real_prefix)
        prefix = sys.real_prefix
    elif hasattr(sys, "base_prefix"):
        logger.notify("Using base prefix %r", sys.base_prefix)
        prefix = sys.base_prefix
    else:
        prefix = sys.prefix
    prefix = os.path.abspath(prefix)
    mkdir(lib_dir)
    fix_lib64(lib_dir, symlink)
    stdlib_dirs = [os.path.dirname(os.__file__)]
    if IS_WIN:
        stdlib_dirs.append(join(os.path.dirname(stdlib_dirs[0]), "DLLs"))
    elif IS_DARWIN:
        stdlib_dirs.append(join(stdlib_dirs[0], "site-packages"))
    if hasattr(os, "symlink"):
        logger.info("Symlinking Python bootstrap modules")
    else:
        logger.info("Copying Python bootstrap modules")
    logger.indent += 2
    try:
        # copy required files...
        for stdlib_dir in stdlib_dirs:
            copy_required_files(stdlib_dir, lib_dir, symlink)
        # ...and modules
        copy_required_modules(home_dir, symlink)
        copy_license(prefix, home_dir, lib_dir, symlink)
    finally:
        logger.indent -= 2
    # ...copy tcl/tk
    if IS_WIN:
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

    if IS_PYPY or IS_WIN:
        standard_lib_include_dir = join(prefix, "include")
    else:
        standard_lib_include_dir = join(prefix, "include", PY_VERSION + ABI_FLAGS)
    if os.path.exists(standard_lib_include_dir):
        copy_include_dir(standard_lib_include_dir, inc_dir, symlink)
    else:
        logger.debug("No include dir %s", standard_lib_include_dir)

    platform_include_dir = distutils.sysconfig.get_python_inc(plat_specific=1)
    if platform_include_dir != standard_lib_include_dir:
        platform_include_dest = distutils.sysconfig.get_python_inc(plat_specific=1, prefix=home_dir)
        if platform_include_dir == platform_include_dest:
            # Do platinc_dest manually due to a CPython bug;
            # not http://bugs.python.org/issue3386 but a close cousin
            platform_include_dest = subst_path(platform_include_dir, prefix, home_dir)
        if platform_include_dest:
            # PyPy's stdinc_dir and prefix are relative to the original binary
            # (traversing virtualenvs), whereas the platinc_dir is relative to
            # the inner virtualenv and ignores the prefix argument.
            # This seems more evolved than designed.
            copy_include_dir(platform_include_dir, platform_include_dest, symlink)

    # pypy never uses exec_prefix, just ignore it
    if os.path.realpath(sys.exec_prefix) != os.path.realpath(prefix) and not IS_PYPY:
        if IS_WIN:
            exec_dir = join(sys.exec_prefix, "lib")
        else:
            exec_dir = join(sys.exec_prefix, "lib", PY_VERSION)
        copy_required_files(exec_dir, lib_dir, symlink)

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

    logger.notify("New %s executable in %s", EXPECTED_EXE, py_executable)
    pc_build_dir = os.path.dirname(sys.executable)
    pyd_pth = os.path.join(lib_dir, "site-packages", "virtualenv_builddir_pyd.pth")
    if IS_WIN and os.path.exists(os.path.join(pc_build_dir, "build.bat")):
        logger.notify("Detected python running from build directory %s", pc_build_dir)
        logger.notify("Writing .pth file linking to build directory for *.pyd files")
        writefile(pyd_pth, pc_build_dir)
    else:
        if os.path.exists(pyd_pth):
            logger.info("Deleting %s (not Windows env or not build directory python)", pyd_pth)
            os.unlink(pyd_pth)

    if sys.executable != py_executable:
        # FIXME: could I just hard link?
        executable = sys.executable
        shutil.copyfile(executable, py_executable)
        make_exe(py_executable)
        if IS_WIN or IS_CYGWIN:
            python_w = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
            if os.path.exists(python_w):
                logger.info("Also created pythonw.exe")
                shutil.copyfile(python_w, os.path.join(os.path.dirname(py_executable), "pythonw.exe"))
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
            if IS_PYPY:
                py_executable_dll_s = [("libpypy-c.dll", "libpypy_d-c.dll")]
            else:
                py_executable_dll_s = [
                    ("python{}.dll".format(sys.version_info[0]), "python{}_d.dll".format(sys.version_info[0])),
                    (
                        "python{}{}.dll".format(sys.version_info[0], sys.version_info[1]),
                        "python{}{}_d.dll".format(sys.version_info[0], sys.version_info[1]),
                    ),
                ]

            for py_executable_dll, py_executable_dll_d in py_executable_dll_s:
                python_dll = os.path.join(os.path.dirname(sys.executable), py_executable_dll)
                python_dll_d = os.path.join(os.path.dirname(sys.executable), py_executable_dll_d)
                python_dll_d_dest = os.path.join(os.path.dirname(py_executable), py_executable_dll_d)
                if os.path.exists(python_dll):
                    logger.info("Also created %s", py_executable_dll)
                    shutil.copyfile(python_dll, os.path.join(os.path.dirname(py_executable), py_executable_dll))
                if os.path.exists(python_dll_d):
                    logger.info("Also created %s", py_executable_dll_d)
                    shutil.copyfile(python_dll_d, python_dll_d_dest)
                elif os.path.exists(python_dll_d_dest):
                    logger.info("Removed %s as the source does not exist", python_dll_d_dest)
                    os.unlink(python_dll_d_dest)
        if IS_PYPY:
            # make a symlink python --> pypy-c
            python_executable = os.path.join(os.path.dirname(py_executable), "python")
            if IS_WIN or IS_CYGWIN:
                python_executable += ".exe"
            logger.info("Also created executable %s", python_executable)
            copyfile(py_executable, python_executable, symlink)

            if IS_WIN:
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

    if os.path.splitext(os.path.basename(py_executable))[0] != EXPECTED_EXE:
        secondary_exe = os.path.join(os.path.dirname(py_executable), EXPECTED_EXE)
        py_executable_ext = os.path.splitext(py_executable)[1]
        if py_executable_ext.lower() == ".exe":
            # python2.4 gives an extension of '.4' :P
            secondary_exe += py_executable_ext
        if os.path.exists(secondary_exe):
            logger.warn(
                "Not overwriting existing {} script {} (you must use {})".format(
                    EXPECTED_EXE, secondary_exe, py_executable
                )
            )
        else:
            logger.notify("Also creating executable in %s", secondary_exe)
            shutil.copyfile(sys.executable, secondary_exe)
            make_exe(secondary_exe)

    if ".framework" in prefix:
        original_python = None
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
        # noinspection PyBroadException
        try:
            mach_o_change(py_executable, os.path.join(prefix, "Python"), "@executable_path/../.Python")
        except Exception:
            e = sys.exc_info()[1]
            logger.warn("Could not call mach_o_change: %s. " "Trying to call install_name_tool instead.", e)
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

    if not IS_WIN:
        # Ensure that 'python', 'pythonX' and 'pythonX.Y' all exist
        py_exe_version_major = "python{}".format(sys.version_info[0])
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
    logger.info('Testing executable with %s %s "%s"', *cmd)
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
    # when addressed over a symlink
    proc_stdout = os.path.normcase(os.path.realpath(proc_stdout))
    norm_home_dir = os.path.normcase(os.path.realpath(home_dir))
    if hasattr(norm_home_dir, "decode"):
        norm_home_dir = norm_home_dir.decode(sys.getfilesystemencoding())
    if proc_stdout != norm_home_dir:
        logger.fatal("ERROR: The executable %s is not functioning", py_executable)
        logger.fatal("ERROR: It thinks sys.prefix is {!r} (should be {!r})".format(proc_stdout, norm_home_dir))
        logger.fatal("ERROR: virtualenv is not compatible with this system or executable")
        if IS_WIN:
            logger.fatal(
                "Note: some Windows users have reported this error when they "
                'installed Python for "Only this user" or have multiple '
                "versions of Python installed. Copying the appropriate "
                "PythonXX.dll to the virtualenv Scripts/ directory may fix "
                "this problem."
            )
        sys.exit(100)
    else:
        logger.info("Got sys.prefix result: %r", proc_stdout)

    pydistutils = os.path.expanduser("~/.pydistutils.cfg")
    if os.path.exists(pydistutils):
        logger.notify("Please make sure you remove any previous custom paths from " "your %s file.", pydistutils)
    # FIXME: really this should be calculated earlier

    fix_local_scheme(home_dir, symlink)

    if site_packages:
        if os.path.exists(site_packages_filename):
            logger.info("Deleting %s", site_packages_filename)
            os.unlink(site_packages_filename)

    return py_executable


def install_activate(home_dir, bin_dir, prompt=None):
    if IS_WIN:
        files = {"activate.bat": ACTIVATE_BAT, "deactivate.bat": DEACTIVATE_BAT, "activate.ps1": ACTIVATE_PS}

        # MSYS needs paths of the form /c/path/to/file
        drive, tail = os.path.splitdrive(home_dir.replace(os.sep, "/"))
        home_dir_msys = (drive and "/{}{}" or "{}{}").format(drive[:1], tail)

        # Run-time conditional enables (basic) Cygwin compatibility
        home_dir_sh = """$(if [ "$OSTYPE" "==" "cygwin" ]; then cygpath -u '{}'; else echo '{}'; fi;)""".format(
            home_dir, home_dir_msys
        )
        files["activate"] = ACTIVATE_SH.replace("__VIRTUAL_ENV__", home_dir_sh)

    else:
        files = {
            "activate": ACTIVATE_SH,
            "activate.fish": ACTIVATE_FISH,
            "activate.csh": ACTIVATE_CSH,
            "activate.ps1": ACTIVATE_PS,
        }
    files["activate_this.py"] = ACTIVATE_THIS

    if sys.version_info >= (3, 4):
        # Add xonsh support
        files["activate.xsh"] = ACTIVATE_XSH

    install_files(home_dir, bin_dir, prompt, files)


def install_files(home_dir, bin_dir, prompt, files):
    if hasattr(home_dir, "decode"):
        home_dir = home_dir.decode(sys.getfilesystemencoding())
    virtualenv_name = os.path.basename(home_dir)
    for name, content in files.items():
        content = content.replace("__VIRTUAL_PROMPT__", prompt or "")
        content = content.replace("__VIRTUAL_WINPROMPT__", prompt or "({}) ".format(virtualenv_name))
        content = content.replace("__VIRTUAL_ENV__", home_dir)
        content = content.replace("__VIRTUAL_NAME__", virtualenv_name)
        content = content.replace("__BIN_NAME__", os.path.basename(bin_dir))
        content = content.replace("__PATH_SEP__", os.pathsep)
        writefile(os.path.join(bin_dir, name), content)


def install_python_config(home_dir, bin_dir, prompt=None):
    if IS_WIN:
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
    # FIXME: this is breaking things, removing for now:
    # distutils_cfg = DISTUTILS_CFG + "\n[install]\nprefix=%s\n" home_dir
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
        # noinspection PyProtectedMember
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
    if IS_PYPY:
        logger.debug("PyPy detected, skipping lib64 symlinking")
        return
    # Check we have a lib64 library path
    if not [p for p in distutils.sysconfig.get_config_vars().values() if isinstance(p, basestring) and "lib64" in p]:
        return

    logger.debug("This system uses lib64; symlinking lib64 to lib")

    assert os.path.basename(lib_dir) == "python{}".format(sys.version[:3]), "Unexpected python lib dir: {!r}".format(
        lib_dir
    )
    lib_parent = os.path.dirname(lib_dir)
    top_level = os.path.dirname(lib_parent)
    lib_dir = os.path.join(top_level, "lib")
    lib64_link = os.path.join(top_level, "lib64")
    assert os.path.basename(lib_parent) == "lib", "Unexpected parent dir: {!r}".format(lib_parent)
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
            "The environment doesn't have a file %s -- please re-run virtualenv " "on this environment to update it",
            activate_this,
        )
    fixup_scripts(home_dir, bin_dir)
    fixup_pth_and_egg_link(home_dir)
    # FIXME: need to fix up distutils.cfg


OK_ABS_SCRIPTS = [
    "python",
    "python{}".format(sys.version[:3]),
    "activate",
    "activate.bat",
    "activate_this.py",
    "activate.fish",
    "activate.csh",
    "activate.xsh",
]


def fixup_scripts(_, bin_dir):
    if IS_WIN:
        new_shebang_args = ("{} /c".format(os.path.normcase(os.environ.get("COMSPEC", "cmd.exe"))), "", ".exe")
    else:
        new_shebang_args = ("/usr/bin/env", sys.version[:3], "")

    # This is what we expect at the top of scripts:
    shebang = "#!{}".format(
        os.path.normcase(os.path.join(os.path.abspath(bin_dir), "python{}".format(new_shebang_args[2])))
    )
    # This is what we'll put:
    new_shebang = "#!{} python{}{}".format(*new_shebang_args)

    for filename in os.listdir(bin_dir):
        filename = os.path.join(bin_dir, filename)
        if not os.path.isfile(filename):
            # ignore child directories, e.g. .svn ones.
            continue
        with open(filename, "rb") as f:
            try:
                lines = f.read().decode("utf-8").splitlines()
            except UnicodeDecodeError:
                # This is probably a binary program instead
                # of a script, so just ignore it.
                continue
        if not lines:
            logger.warn("Script %s is an empty file", filename)
            continue

        old_shebang = lines[0].strip()
        old_shebang = old_shebang[0:2] + os.path.normcase(old_shebang[2:])

        if not old_shebang.startswith(shebang):
            if os.path.basename(filename) in OK_ABS_SCRIPTS:
                logger.debug("Cannot make script %s relative", filename)
            elif lines[0].strip() == new_shebang:
                logger.info("Script %s has already been made relative", filename)
            else:
                logger.warn(
                    "Script %s cannot be made relative (it's not a normal script that starts with %s)",
                    filename,
                    shebang,
                )
            continue
        logger.notify("Making script %s relative", filename)
        script = relative_script([new_shebang] + lines[1:])
        with open(filename, "wb") as f:
            f.write("\n".join(script).encode("utf-8"))


def relative_script(lines):
    """Return a script that'll work in a relocatable environment."""
    activate = (
        "import os; "
        "activate_this=os.path.join(os.path.dirname(os.path.realpath(__file__)), 'activate_this.py'); "
        "exec(compile(open(activate_this).read(), activate_this, 'exec'), { '__file__': activate_this}); "
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
    for a_path in sys_path:
        if not a_path:
            a_path = "."
        if not os.path.isdir(a_path):
            continue
        a_path = os.path.normcase(os.path.abspath(a_path))
        if not a_path.startswith(home_dir):
            logger.debug("Skipping system (non-environment) directory %s", a_path)
            continue
        for filename in os.listdir(a_path):
            filename = os.path.join(a_path, filename)
            if filename.endswith(".pth"):
                if not os.access(filename, os.W_OK):
                    logger.warn("Cannot write .pth file %s, skipping", filename)
                else:
                    fixup_pth_file(filename)
            if filename.endswith(".egg-link"):
                if not os.access(filename, os.W_OK):
                    logger.warn("Cannot write .egg-link file %s, skipping", filename)
                else:
                    fixup_egg_link(filename)


def fixup_pth_file(filename):
    lines = []
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
        logger.info("No changes to .pth file %s", filename)
        return
    logger.notify("Making paths in .pth file %s relative", filename)
    with open(filename, "w") as f:
        f.write("\n".join(lines) + "\n")


def fixup_egg_link(filename):
    with open(filename) as f:
        link = f.readline().strip()
    if os.path.abspath(link) != link:
        logger.debug("Link in %s already relative", filename)
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
    else:
        dest_filename = None
    dest = os.path.normpath(os.path.abspath(dest))
    source = os.path.normpath(os.path.abspath(source))
    dest_parts = dest.strip(os.path.sep).split(os.path.sep)
    source_parts = source.strip(os.path.sep).split(os.path.sep)
    while dest_parts and source_parts and dest_parts[0] == source_parts[0]:
        dest_parts.pop(0)
        source_parts.pop(0)
    full_parts = [".."] * len(source_parts) + dest_parts
    if not dest_is_directory and dest_filename is not None:
        full_parts.append(dest_filename)
    if not full_parts:
        # Special case for the current directory (otherwise it'd be '')
        return "./"
    return os.path.sep.join(full_parts)


FILE_PATH = __file__ if os.path.isabs(__file__) else os.path.join(os.getcwd(), __file__)


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
    filename = FILE_PATH
    if filename.endswith(".pyc"):
        filename = filename[:-1]
    with codecs.open(filename, "r", encoding="utf-8") as f:
        content = f.read()
    py_exe = "python{}".format(python_version)
    content = "#!/usr/bin/env {}\n# WARNING: This file is generated\n{}".format(py_exe, content)
    # we build the string as two, to avoid replacing here, but yes further done
    return content.replace("# EXTEND - " "bootstrap here", extra_text)


# EXTEND - bootstrap here


def convert(s):
    b = base64.b64decode(s.encode("ascii"))
    return zlib.decompress(b).decode("utf-8")


# file site.py
SITE_PY = convert(
    """
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
aygG/wu2AIfx
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
eJytVm1v2zYQ/q5fcZUdyClqGVuHfQgwDGnjIQYSO3DcAMM6yLREWxxo0iMpty7243ekLImy5RQY
lg+RJT73fvfwerDImYY14xS2hTawolBomuE/Jjaw1LJQKYUVEyOSGrYnhsZrpvMlvP3CTM4EEFCF
EBZsv8MAcmN2N6ORfdM55TxO5RauQVOtmRRv46AHdxKENFYQmIGMKZoafoiDYF0ItCIFJCuic7Y+
JDtichhmEH6UYk+V0WjQGXIHRoKWW2od2YAVgZQIQHVyI9g3GgaAf5oaJ3JU1idqs68PrFB10ID+
+OFPh1hL5QzhR2UAo/UxP8bx8Ijr0Bb2m5ebfq2kdImKrHymuQQPGNgDLwvW2qUsuHDPs+CS05GF
0pSNHf4BoyC6iSD6LKITkxmt6mztReOvWKA9U6YgnIo9bGVGgYgMtZtCCWva5BSrqbaEY1gIlWJL
hYkjZ7WHQJsYyTP/FPZEMbLiVDsUW4Oh2HxDgWlLZg93yctkvvh0+5A83S7uwzrFPddcGrtrg81X
rGxruUYbuk7zfzKtC6pHP73/GQg3VGFLW12Qo/Mc81TrrGwPygT9Nnm+T17G8+fJbFomKoxDCD+L
8BqbAobcwPtatir7cPO11D5oV+w8lutalnJNLys6l2wEj71Ty1DoBrvCfie9vy/uZ9P72eM4DM78
qM9OvakPXvejDXvFG5fzp/ns8WmRzDD388nd2C/6M2rHhqbbnTkAlyl22tINYlK1rUv30nYj4Vx+
cT2p6FbuESrXsHTgnZKoYVlRWyWr0fNl3A6Fw7n6wPNorIim3lxE+sRGOSLaSEWdM1KxDROEN3Z8
8+DJdgFSSHCAEg/1PQl6JtFZq67Mt6t1RFdFHU9f2lUMHaXgaITw5heIhBQZflaFJREatYrI18Pq
7E23z7tDJtPuo4aXLoTrXxgXIP5s1lG6SHvwSdhImVKU0z3xGSoOPE5sxxcE1bB4+YEwSbzXJAmt
/v+PuP4jYVWennEFklbrsu2XPFXz02VBh3QJbHFX2PfCHyXJh8k0md4+jjETR5E638t+wxJL21P4
MQ7KJwz/hhMO6XbF46kuPPW1tC+7pt92B5Pjh+G2/HZcEhy65qtv7ciSu8nz7YeH8XF+wuN991Hu
Dm7k0wKbCRupTQy1bYKUcTqjRxpqTb4/9Gcz3YJ3cgIOHtnTlkN9bYgp9Du33XgyGlHErmN6x8kB
N7MzUrTmS+FKiU+KT6WTEhcUxXBNQK17fGa/epjJ2m5+7+Avu2vuFN1hip1z/nIgyJY2tv37opms
I2klzT3hyqiYMGuIrvSVjjrhMMBYklRyjL3cWl65kht1gyt9DVGHMAxweKj1uN0doae24tIyBfOO
a6FOZy1jZzukdvvqN1kPccDLjbwGdtJ8m72rgeki+xOnXcf/CzFcuJM=
"""
)

# file activate.csh
ACTIVATE_CSH = convert(
    """
eJx9VNtO4zAQffdXDKEiUEFhX8t22bJFWqRyEVuQVkKy3Hi6sZQ44Dit+sK379hJittG5KGqPZdz
fOZyCLNUlbBQGUJelRbmCFWJElbKphCVRWUShLnS5yKxaiksDpIyjaC/MEUO9Lc/YIfwt6ggEVoX
FkylQVmQymBis7Wz/jJIcRLma5iIpZIIEwXXmSgVfJf+Qs5//suFygZJkf8YMFaiBY2rTGkcxa8s
ZkxkSpQgsWUBsUVi27viD9MJf7l9mj2Pp/xxPPsNByO4gKMjoCSol+Dvot6e3/A9cl6VdmB71ksw
mIoyvYROnKeHu8dZiARvpMebHe0CeccvoLz9sjY5tq3h5v6lgY5eD4b9yGFFutCSrkzlRMAm554y
we3bWhYJqXcIzx5bGYMZLoW2sBRGiXmG5YAFsdsIvhA7rCDiPDhyHtXl2lOQpGhkZtuVCKKH7+ec
X9/e8/vx3Q3nw00EfWoBxwFWrRTBeSWiE7Apagb0OXRKz7XIEUbQFcMwK7HLOT6OtwlZQo9PIGao
pVrULKj64Ysnt3/G19ObtgkCJrXzF74jRz2MaCnJgtcN5B7wLfK2DedOp4vGydPcet5urq2XBEZv
DcnQpBZVJt0KUBqEa4YzpS0a3x7odFOm0Dlqe9oEkN8qVUlK01/iKfSa3LRRKmqkBc2vBKFpmyCs
XG4d2yYyEQZBzIvKOgLN+JDveiVoaXyqedVYOkTrmCRqutrfNVHr6xMFBhh9QD/qNQuGLvq72d03
3Jy2CtGCf0rca/tp+N4BXqsflKquRr0L2sjmuClOu+/8/NKvTQsNZ3l9ZqxeTew//1a6EA==
"""
)

# file activate.xsh
ACTIVATE_XSH = convert(
    """
eJyNU11PwjAUfe+vuNY9sIj7ASQ+YCSBRD6i02gIaSq7gyWjXdqyaIz/3XYwVmB+9GFZ78c57T2n
lNIXKfQa+NJkJTcIeqmywkAqFZSZMlueoygppSRVcgPvrjgyUuYask0hlYEVGqaxAK6B7f8JSTAF
lmCN2uFqpcMeAbuyFGjxkcglhUwAzzOuUe9SbiWY18H5vm5B6sbgM4qir8jSdCib3t+x59FD/NS/
Z7N+PKRdoDRskAIXhBsIziqPyFrSf9O9xsPpZDgdD85JD6lz6kPqtwM0RYdx1bnB5Lka2u5cxzML
vKLWTjZ7mI5n8b8A9rUNjpAiQW3U1gmKFIQ0lXpW1gblEh4xT6EuvGjXtHGFE5ZcwlZotGhKYY4l
FwZKrjL+lqMmvoXmp4dYhKQV1M7d6yPEv5jNKcqYf1VGbcmZB5x4lRcCfzfvLXaBiCdJ5wj46uD+
Tmg3luR2NGGT/nhgGbpgX48wN7HaYhcUFjlfYrULCTkxWru36jF59rJ9NlJlf7JQde5j11VS+yZr
0d22eUPaxdycLKMTvqWjR3610emDtgTu36ylcJe83rhv/di/AYN1UZY=
"""
)

# file activate.bat
ACTIVATE_BAT = convert(
    """
eJyVk1FLhEAUhd8X/A8XWSkf28dCyMUpBR3FzAiCS+WYwq4TOdXfb0Z3dTJdyCfveO85n8frNXut
OPCyNFbGqmUCzDxIs3s3REJzB1GrEE3VVJdQsLJuWAEYh97QkaRxlGRwbqxAXp1Uf+RYM32W1LKB
7Vp2nJC6DReD9m+5qeQ6Wd+a/SN7dlzn9oI7dxsSXJCcoXOskfLgYXdv/j8LnXiM8iGg/RmiZmOr
bFMSgcebMwGfKhgbBIfnL14X8P7BX3Zs38J3LSoQFdtD3YCVuJlvnfgmj5kfUz+OCLxxqUWoF9zk
qtYAFyZkBsO9ArzUh/td0ZqP9IskElTFMsnwb4/GqeoLPUlZT5dJvf8Id5hQIONynUSa2G0Wc+m8
Z+w2w4/Tt2hbYT0hbgOK1I0I4tUw/QOTZfLE
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
eJytVcFu2zAMvfsrWNfYEmx2sWuGHVIkQAO0adBkvWyDoMh0I0CWDElOGwz598p2HDt20w3YdLP5
SD2Sj9QlrDbcQMIFQpobC2uEWFkwKtcMY0i0SmGhlpuvsFM5MCqls+pcArcQc43Mil0EEwXWxRlB
BNEVZZZvqcUoM188LzBM88yOVjezJVmMVzfwDYJ0x+VWMWq5klG6YypNqYyjjNrN0eF6vJySyezB
4U0muA0LKww0GiW2WH35wTHsVRT5QwgXVKO0npfkkhXR4UmoNRWjGGtagx/mmVu2+QXBXMkJGqvz
woRD77cH7vAEBtb9rq7YUs3pWuCI3N9OyOPsYfV9fFveOCzRlU9xApTbUZ3hebcjXmOqXCI1Evwe
1IfQMJXhIYnSc++9QbLOdkSUiMmWa5tTQTLXvMz2aB7Blb1g+55/ly+3mDYX/jzn0eJZFqbOazp/
7DEqQjjMaae7XhAKpMmbbHpI1FppWgnAOG1Lp1KmpOUyxy67i54MTtldwhJFAvEBcfF+PRqdvY/L
drFiByr7vlwrc0Ui29mNs4QplH8hoPrJFE6XkEuDFrjWKHBLpT2q1XgNEQilknGToJvJdrFc++tR
83o1d8bWp/M88OtJtUDW+vfak+B3Y14Rcj2bk/n4bkrcKWBkOV0Q4sOnVoyqNR1fR3I5vr6dksXD
/d1iVU9st3rnNNk01fcPtT+diDccT8ajFavg55OmBiWhIolQulH2uyrqNfh0thpgJblxHLuNisDc
TnYbONOY8BewqvyJL9w4KT9BJ0hxnrXTWbhRbpWfYackPgsu8cTtw1/ugH2rbCgM/nuWtJMcy3Wx
wQ+5fYZ17h4aJT8Wz41hVMfu5YnOpjwIBn/eITAcwn+rxN57BRHvOEk=
"""
)

# file distutils-init.py
DISTUTILS_INIT = convert(
    """
eJytV21v5DQQ/p5fMaRCJLANcAcSqlghuBdUcRzo6BdUnSI3cXZNs3bO9m679+uZsbOJnWR7fKBS
u65nPC/PvK7YdUpbUCYR/mSOw/GBaSnkxiTJBaiuUjUHYUAqCwwOQts9a7k8wE7V+5avwCh44FAx
CXuDnBasgkbIGuyWg7F1K+5Q0LWTzaT9DG7wgdL3oCR0x+64QkaUv9sbC3ccdXjBeMssaG5EzQ0I
SeJQDkq77I52q+TXyCcawevLx+JYfIRaaF5ZpY8nP7ztSYIEyXYc1uhu0TG7LfobIhm7t6I1Jd0H
HP8oIbMJe+YFFmXZiJaXZb6CdBCQ5olohudS6R0dslhBDuuZEdnszSA/v0oAf07xKOiQpTcIaxCG
QQN0rLpnG0TQwucGWNdxpg1FA1H1+IEhHFpVMSsQfWb85dFYvhsF/YS+8NZwr710lpdlIaTh2mbf
rGDqFFxgdnxgV/D6h2ffukcIBUotDlwbVFQK2Sj4EbLnK/iud8px+TjhRzLcac7acvRpTdSiVawu
fVpkaTk6PzKmK3irJJ/atoIsRRL9kpw/f/u1fHn97tWLmz/e/Z3nTunoaWwSfmCuFTtWbYXkmFUD
z9NJMzUgLdF9YRHA7pjmgxByiWvv31RV8Zfa64q/xix449jOOz0JxejH2QB8HwQg8NgeO26SiDIL
heMpfndxuMFz5p0oKI1H1TGgi6CSwFiX6XgVgUEsBd2WjVa70msKFa56CPOnbZ5I9EnkZZL0jP5M
o1LwR9Tb51ssMfdmX8AL1R1d9Wje8gP2NSw7q8Xd3iKMxGL1cUShLDU/CBeKEo2KZRYh1efkY8U7
Cz+fJL7SWulRWseM6WvzFOBFqQMxScjhoFX0EaGLFSVKpWQjNuSXMEi4MvcCa3Jw4Y4ZbtAWuUl6
095iBAKrRga0Aw80OjAhqy3c7UVbl/zRwlgZUCtu5BcW7qV6gC3+YpPacOvwxFCZoJc7OVuaFQ84
U9SDgUuaMVuma2rGvoMRC3Y8rfb92HG6ee1qoNO8EY8YuL4mupbZBnst9eIUhT5/lnonYoyKSu12
TNbF6EGP2niBDVThcbjwyVG1GJ+RK4tYguqreUODkrXiIy9VRy3ZZIa3zbRC0W68LRAZzfQRQ4xt
HScmNbyY01XSjHUNt+8jNt6iSMw3aXAgVzybPVkFAc3/m4rZHRZvK+xpuhne5ZOKnz0YB0zUUClm
LrV9ILGjvsEUSfO48COQi2VYkyfCvBjc4Z++GXgB09sgQ9YQ5MJFoIVOfVaaqyQha2lHKn3huYFP
KBJb8VIYX/doeTHjSnBr8YkT34eZ07hCWMOimh6LPrMQar8cYTF0yojHdIw37nPavenXpxRHWABc
s0kXJujs0eKbKdcs4qdgR4yh1Y5dGCJlMdNoC5Y5NgvcbXD9adGIzAEzLy/iKbiszYPA/Wtm8UIJ
OEGYljt14Bk9z5OYROuXrLMF8zW3ey09W+JX0E+EHPFZSIMwvcYWHucYNtXSb8u4AtCAHRiLmNRn
1UCevMyoabqBiRt3tcYS9fFZUw/q4UEc/eW8N/X3Tn1YyyEec3NjpSeVWMXJOTNx5tWqcsNwLu5E
TM5hEMJTTuGZyMPGdQ5N+r7zBJpInqNJjbjGkUbUs+iGTEAt63+Ee2ZVbNMnwacF6yz4AXEZ/Ama
5RTNk7yefGB+5ESiAtoi/AE9+5LpjemBdfj0Ehf09Lzht5qzCwT9oL00zZZaWjzEWjfEwoU9mMiD
UbThVzZ34U7fXP+C315S91UcO9rAFLen4fr29OA9WnOyC1c8Zu5xNaLeyNo2WNvPmkCtc2ICqidc
zmg+LaPu/BXc9srfx9pJbJiSw5NZkgXxWMiyBWpyNjdmeRbmzb+31cHS
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
eJylVE1v2zAMvetXENqhNpZ5wHoL0EMOBdqh64Kt3RAEhaE4TMzOlgxJ+ULR/z7Sdpr041BsOUSS
9fj0SD5Jaz0qIq1NRFiTjytToV3DwnkoVt6jjUA2om888v9QqduAgFssEtegTWJJIV9QhWnm0cyT
dAAPJ3n7Jc9PhvC0/5hmSt3wCgpjYYawCjiHTYkWdm4F9SpE+QS8iVsKkewSxrtYOnt8/gCsi0z6
TOuM7OemhWZKa62obpyP4MJ+Fiji03wXlIp+N1TAv71ShdsCmwjXpsZz753vtr0hljQKAX0kZ9ud
RE+O9f5TKVKdKvUBOCcOnEsCEB2MRzcX0NKAwIBHsoHm2CYsoDl5LKLzu1TxMuclnHGeWWNimfHK
svxkvzazIGOyl5Cmire4YOSdnWo5Td8d4gM22b0jm0x76jv4CIeAbIkx6YIGoHWahaaimByCmV7N
DFfktaKesM257xtI4zhBT8sygpm59YsMn2n9dfnj5nZ0lZ9f/2olyzlCZubzYzNAH1Cza0Pb9U+N
Kf6YJUp5BVg6blvT26ozRI1FaSyFWl3+zMeT8YT5SxNMjD5hs3Cyza7Z5Wv0gS2Qk1047h5jv05u
Lr5fM5pRWVOZyHemzkI0PoYNceH1vVkbxtICnuCdr0Ra3ksLRwVr6y/J8alXNJNKH2cRmAyrjk6U
vp/sNUvALpqpfl++zALOzkBvyJ5+0S2oO5JxXcx/piDhBwHvJas6sq55D486E6EmSo+yvjnT4eld
+saBii/aWlLEDi7cqRJUxg6SkW2XPBPB2wzke1zlHLyg7b5C7UIdpkdu/CYmFpcxKb9tTFeHvfEW
bEt+khbtQs4f8N0GrneByuKGWSp+9I7V9bPpUAw/pfZFJgkSODeE2qdQSDg5uatvYvb76i9zKfxE
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
maxint = MAJOR == 3 and getattr(sys, "maxsize") or getattr(sys, "maxint")


class FileView(object):
    """
    A proxy for file-like objects that exposes a given view of a file.
    Modified from macholib.
    """

    def __init__(self, file_obj, start=0, size=maxint):
        if isinstance(file_obj, FileView):
            self._file_obj = file_obj._file_obj
        else:
            self._file_obj = file_obj
        self._start = start
        self._end = start + size
        self._pos = 0

    def __repr__(self):
        return "<fileview [{:d}, {:d}] {!r}>".format(self._start, self._end, self._file_obj)

    def tell(self):
        return self._pos

    def _checkwindow(self, seek_to, op):
        if not (self._start <= seek_to <= self._end):
            raise IOError(
                "{} to offset {:d} is outside window [{:d}, {:d}]".format(op, seek_to, self._start, self._end)
            )

    def seek(self, offset, whence=0):
        seek_to = offset
        if whence == os.SEEK_SET:
            seek_to += self._start
        elif whence == os.SEEK_CUR:
            seek_to += self._start + self._pos
        elif whence == os.SEEK_END:
            seek_to += self._end
        else:
            raise IOError("Invalid whence argument to seek: {!r}".format(whence))
        self._checkwindow(seek_to, "seek")
        self._file_obj.seek(seek_to)
        self._pos = seek_to - self._start

    def write(self, content):
        here = self._start + self._pos
        self._checkwindow(here, "write")
        self._checkwindow(here + len(content), "write")
        self._file_obj.seek(here, os.SEEK_SET)
        self._file_obj.write(content)
        self._pos += len(content)

    def read(self, size=maxint):
        assert size >= 0
        here = self._start + self._pos
        self._checkwindow(here, "read")
        size = min(size, self._end - here)
        self._file_obj.seek(here, os.SEEK_SET)
        read_bytes = self._file_obj.read(size)
        self._pos += len(read_bytes)
        return read_bytes


def read_data(file, endian, num=1):
    """
    Read a given number of 32-bits unsigned integers from the given file
    with the given endianness.
    """
    res = struct.unpack(endian + "L" * num, file.read(num * 4))
    if len(res) == 1:
        return res[0]
    return res


def mach_o_change(at_path, what, value):
    """
    Replace a given name (what) in any LC_LOAD_DYLIB command found in
    the given binary with a new name (value), provided it's shorter.
    """

    def do_macho(file, bits, endian):
        # Read Mach-O header (the magic number is assumed read by the caller)
        cpu_type, cpu_sub_type, file_type, n_commands, size_of_commands, flags = read_data(file, endian, 6)
        # 64-bits header has one more field.
        if bits == 64:
            read_data(file, endian)
        # The header is followed by n commands
        for _ in range(n_commands):
            where = file.tell()
            # Read command header
            cmd, cmd_size = read_data(file, endian, 2)
            if cmd == LC_LOAD_DYLIB:
                # The first data field in LC_LOAD_DYLIB commands is the
                # offset of the name, starting from the beginning of the
                # command.
                name_offset = read_data(file, endian)
                file.seek(where + name_offset, os.SEEK_SET)
                # Read the NUL terminated string
                load = file.read(cmd_size - name_offset).decode()
                load = load[: load.index("\0")]
                # If the string is what is being replaced, overwrite it.
                if load == what:
                    file.seek(where + name_offset, os.SEEK_SET)
                    file.write(value.encode() + "\0".encode())
            # Seek to the next command
            file.seek(where + cmd_size, os.SEEK_SET)

    def do_file(file, offset=0, size=maxint):
        file = FileView(file, offset, size)
        # Read magic number
        magic = read_data(file, BIG_ENDIAN)
        if magic == FAT_MAGIC:
            # Fat binaries contain nfat_arch Mach-O binaries
            n_fat_arch = read_data(file, BIG_ENDIAN)
            for _ in range(n_fat_arch):
                # Read arch header
                cpu_type, cpu_sub_type, offset, size, align = read_data(file, BIG_ENDIAN, 5)
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

    with open(at_path, "r+b") as f:
        do_file(f)


if __name__ == "__main__":
    main()
