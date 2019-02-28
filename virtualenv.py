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

__version__ = "16.4.3"
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

IS_JYTHON = sys.platform.startswith("java")
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
elif IS_JYTHON:
    EXPECTED_EXE = "jython"
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
                        at_path = winreg.QueryValue(python_core, "{}\\InstallPath".format(version))
                    except WindowsError:
                        continue
                    exes[version] = join(at_path, "python.exe")
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

    if options.python and not os.environ.get("VIRTUALENV_INTERPRETER_RUNNING"):
        env = os.environ.copy()
        interpreter = resolve_interpreter(options.python)
        if interpreter == sys.executable:
            logger.warn("Already using interpreter {}".format(interpreter))
        else:
            logger.notify("Running virtualenv with interpreter {}".format(interpreter))
            env["VIRTUALENV_INTERPRETER_RUNNING"] = "true"
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
    if IS_JYTHON:
        extra_args.append("--no-cache")

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
        "JYTHONPATH": python_path,  # for Jython < 3.x
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
        extra_env={"PYTHONPATH": python_path, "JYTHONPATH": python_path},
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
    if IS_JYTHON:
        lib_dir = join(home_dir, "Lib")
        inc_dir = join(home_dir, "Include")
        bin_dir = join(home_dir, "bin")
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
                and sys.platform == "darwin"
                and not (IS_PYPY or filename.endswith(join("lib-dynload", "readline.so")))
            ):
                dst_filename = join(dst_prefix, "lib", "python{}".format(sys.version[:3]), "readline.so")
            elif modname == "readline" and sys.platform == "win32":
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
    for license_path in (
        # posix cpython
        os.path.join(prefix, os.path.relpath(lib_dir, dst_prefix), "LICENSE.txt"),
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
        elif IS_JYTHON:
            exec_dir = join(sys.exec_prefix, "Lib")
        else:
            exec_dir = join(sys.exec_prefix, "lib", PY_VERSION)
        copy_required_files(exec_dir, lib_dir, symlink)

    if IS_JYTHON:
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
            if sys.platform in ("win32", "cygwin"):
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
    if IS_WIN or IS_JYTHON and getattr(os, "_name", None) == "nt":
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
        content = content.replace("__VIRTUAL_WINPROMPT__", prompt or "({})".format(virtualenv_name))
        content = content.replace("__VIRTUAL_ENV__", home_dir)
        content = content.replace("__VIRTUAL_NAME__", virtualenv_name)
        content = content.replace("__BIN_NAME__", os.path.basename(bin_dir))
        content = content.replace("__PATH_SEP__", os.pathsep)
        writefile(os.path.join(bin_dir, name), content)


def install_python_config(home_dir, bin_dir, prompt=None):
    if sys.platform == "win32" or IS_JYTHON and getattr(os, "_name", None) == "nt":
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
DFVPDhmDAiVyzTGUonQ9edEj7VRYQ9H7X+4V6Ls=
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
eJyNVMtu2zAQvOsrNrLQ2miloFcXPdiwgRhwHCN2c2kLgqZWMQGKFEhKqVHky3LoJ/UXSlqWX3LS
8ibtzHJ2d5Z/Xn53YLnmBjIuEPLSWFghpMqCUaVmmEKmVQ5ztVh/ho0qgVEpXVSXEriFlGtkVmwS
GCmwLk8fEkiuKbO8ohaTwnwKgsgwzQvbX95MFmQ+WN7AF4jyDZeVYtRyJZN8w1SeU5kmBbXrPWE4
WIzJaHLv8KYQ3MY+Cl2NRokK668w2qe9TpKwB/GcapQ2CLJSMp8dHoVaUdFPsZHV/WaeuGXrHxDN
lByhsbr0IewFvwJwh2fQte53fUVFNacrgX1yNx2Rh8n98utgur2xt0XXHH8ilFW/qfB12h6vMVeu
kAYJYQsaQmyYKnBXxJb5HFwQ2VTbJ0qkpOLallSQwg2vsC2Ze3Ad92rf4p/r5Rbzw4XfX2Mc6dw2
pqlrPHtoKfIpHOZ00ucsiAXS7KKaFhK1VprWBjDO29K5lClpuSzxXN1Vywan6jqwQJFBukNcvd2P
g8/exhWbVLGdlOe2XetwLaLY2LWLxDls/0JE9aPxpA6U0qAFrjUKrKi0e7ea4CAEYqlkeijQ7eRx
s9z4m1ULWj13waNPx9zpa1nVIxv/B8ebEJ7nvCZkOJmR2eB2TNzxMLIYzwkJ4cNRjno0Z1wncjEY
Tsdkfn93O182G3vevdc8eRhqGO56f7oRF4gn63GUqzWxS9d0YJCmQKHQmPGfYP0zicBK7R8pqCkf
YVW6t1TJ9/5FNYzq1D2uyT7Hk3bOidfKPc5hN+r+e0Wg14NwO3R8ElwejPjuPxbdu/EvkRDrCw==
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
