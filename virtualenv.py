#!/usr/bin/env python
"""Create a "virtual" Python installation
"""

__version__ = "12.1.dev0"
virtualenv_version = __version__  # legacy

import base64
import sys
import os
import codecs
import optparse
import re
import shutil
import logging
import tempfile
import zlib
import errno
import glob
import distutils.sysconfig
from distutils.util import strtobool
import struct
import subprocess
import tarfile

if sys.version_info < (2, 6):
    print('ERROR: %s' % sys.exc_info()[1])
    print('ERROR: this script requires Python 2.6 or greater.')
    sys.exit(101)

try:
    basestring
except NameError:
    basestring = str

try:
    import ConfigParser
except ImportError:
    import configparser as ConfigParser

join = os.path.join
py_version = 'python%s.%s' % (sys.version_info[0], sys.version_info[1])

is_jython = sys.platform.startswith('java')
is_pypy = hasattr(sys, 'pypy_version_info')
is_win = (sys.platform == 'win32')
is_cygwin = (sys.platform == 'cygwin')
is_darwin = (sys.platform == 'darwin')
abiflags = getattr(sys, 'abiflags', '')

user_dir = os.path.expanduser('~')
if is_win:
    default_storage_dir = os.path.join(user_dir, 'virtualenv')
else:
    default_storage_dir = os.path.join(user_dir, '.virtualenv')
default_config_file = os.path.join(default_storage_dir, 'virtualenv.ini')

if is_pypy:
    expected_exe = 'pypy'
elif is_jython:
    expected_exe = 'jython'
else:
    expected_exe = 'python'

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
        try:
            python_core = winreg.CreateKey(winreg.HKEY_LOCAL_MACHINE,
                    "Software\\Python\\PythonCore")
        except WindowsError:
            # No registered Python installations
            return {}
        i = 0
        versions = []
        while True:
            try:
                versions.append(winreg.EnumKey(python_core, i))
                i = i + 1
            except WindowsError:
                break
        exes = dict()
        for ver in versions:
            try:
                path = winreg.QueryValue(python_core, "%s\\InstallPath" % ver)
            except WindowsError:
                continue
            exes[ver] = join(path, "python.exe")

        winreg.CloseKey(python_core)

        # Add the major versions
        # Sort the keys, then repeatedly update the major version entry
        # Last executable (i.e., highest version) wins with this approach
        for ver in sorted(exes):
            exes[ver[0]] = exes[ver]

        return exes

REQUIRED_MODULES = ['os', 'posix', 'posixpath', 'nt', 'ntpath', 'genericpath',
                    'fnmatch', 'locale', 'encodings', 'codecs',
                    'stat', 'UserDict', 'readline', 'copy_reg', 'types',
                    're', 'sre', 'sre_parse', 'sre_constants', 'sre_compile',
                    'zlib']

REQUIRED_FILES = ['lib-dynload', 'config']

majver, minver = sys.version_info[:2]
if majver == 2:
    if minver >= 6:
        REQUIRED_MODULES.extend(['warnings', 'linecache', '_abcoll', 'abc'])
    if minver >= 7:
        REQUIRED_MODULES.extend(['_weakrefset'])
elif majver == 3:
    # Some extra modules are needed for Python 3, but different ones
    # for different versions.
    REQUIRED_MODULES.extend(['_abcoll', 'warnings', 'linecache', 'abc', 'io',
                             '_weakrefset', 'copyreg', 'tempfile', 'random',
                             '__future__', 'collections', 'keyword', 'tarfile',
                             'shutil', 'struct', 'copy', 'tokenize', 'token',
                             'functools', 'heapq', 'bisect', 'weakref',
                             'reprlib'])
    if minver >= 2:
        REQUIRED_FILES[-1] = 'config-%s' % majver
    if minver >= 3:
        import sysconfig
        platdir = sysconfig.get_config_var('PLATDIR')
        REQUIRED_FILES.append(platdir)
        # The whole list of 3.3 modules is reproduced below - the current
        # uncommented ones are required for 3.3 as of now, but more may be
        # added as 3.3 development continues.
        REQUIRED_MODULES.extend([
            #"aifc",
            #"antigravity",
            #"argparse",
            #"ast",
            #"asynchat",
            #"asyncore",
            "base64",
            #"bdb",
            #"binhex",
            #"bisect",
            #"calendar",
            #"cgi",
            #"cgitb",
            #"chunk",
            #"cmd",
            #"codeop",
            #"code",
            #"colorsys",
            #"_compat_pickle",
            #"compileall",
            #"concurrent",
            #"configparser",
            #"contextlib",
            #"cProfile",
            #"crypt",
            #"csv",
            #"ctypes",
            #"curses",
            #"datetime",
            #"dbm",
            #"decimal",
            #"difflib",
            #"dis",
            #"doctest",
            #"dummy_threading",
            "_dummy_thread",
            #"email",
            #"filecmp",
            #"fileinput",
            #"formatter",
            #"fractions",
            #"ftplib",
            #"functools",
            #"getopt",
            #"getpass",
            #"gettext",
            #"glob",
            #"gzip",
            "hashlib",
            #"heapq",
            "hmac",
            #"html",
            #"http",
            #"idlelib",
            #"imaplib",
            #"imghdr",
            "imp",
            "importlib",
            #"inspect",
            #"json",
            #"lib2to3",
            #"logging",
            #"macpath",
            #"macurl2path",
            #"mailbox",
            #"mailcap",
            #"_markupbase",
            #"mimetypes",
            #"modulefinder",
            #"multiprocessing",
            #"netrc",
            #"nntplib",
            #"nturl2path",
            #"numbers",
            #"opcode",
            #"optparse",
            #"os2emxpath",
            #"pdb",
            #"pickle",
            #"pickletools",
            #"pipes",
            #"pkgutil",
            #"platform",
            #"plat-linux2",
            #"plistlib",
            #"poplib",
            #"pprint",
            #"profile",
            #"pstats",
            #"pty",
            #"pyclbr",
            #"py_compile",
            #"pydoc_data",
            #"pydoc",
            #"_pyio",
            #"queue",
            #"quopri",
            #"reprlib",
            "rlcompleter",
            #"runpy",
            #"sched",
            #"shelve",
            #"shlex",
            #"smtpd",
            #"smtplib",
            #"sndhdr",
            #"socket",
            #"socketserver",
            #"sqlite3",
            #"ssl",
            #"stringprep",
            #"string",
            #"_strptime",
            #"subprocess",
            #"sunau",
            #"symbol",
            #"symtable",
            #"sysconfig",
            #"tabnanny",
            #"telnetlib",
            #"test",
            #"textwrap",
            #"this",
            #"_threading_local",
            #"threading",
            #"timeit",
            #"tkinter",
            #"tokenize",
            #"token",
            #"traceback",
            #"trace",
            #"tty",
            #"turtledemo",
            #"turtle",
            #"unittest",
            #"urllib",
            #"uuid",
            #"uu",
            #"wave",
            #"weakref",
            #"webbrowser",
            #"wsgiref",
            #"xdrlib",
            #"xml",
            #"xmlrpc",
            #"zipfile",
        ])
    if minver >= 4:
        REQUIRED_MODULES.extend([
            'operator',
            '_collections_abc',
            '_bootlocale',
        ])

if is_pypy:
    # these are needed to correctly display the exceptions that may happen
    # during the bootstrap
    REQUIRED_MODULES.extend(['traceback', 'linecache'])

class Logger(object):

    """
    Logging object for use in command-line script.  Allows ranges of
    levels, to avoid some redundancy of displayed information.
    """

    DEBUG = logging.DEBUG
    INFO = logging.INFO
    NOTIFY = (logging.INFO+logging.WARN)/2
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
                raise TypeError(
                    "You may give positional or keyword arguments, not both")
        args = args or kw
        rendered = None
        for consumer_level, consumer in self.consumers:
            if self.level_matches(level, consumer_level):
                if (self.in_progress_hanging
                    and consumer in (sys.stdout, sys.stderr)):
                    self.in_progress_hanging = False
                    sys.stdout.write('\n')
                    sys.stdout.flush()
                if rendered is None:
                    if args:
                        rendered = msg % args
                    else:
                        rendered = msg
                    rendered = ' '*self.indent + rendered
                if hasattr(consumer, 'write'):
                    consumer.write(rendered+'\n')
                else:
                    consumer(rendered)

    def start_progress(self, msg):
        assert not self.in_progress, (
            "Tried to start_progress(%r) while in_progress %r"
            % (msg, self.in_progress))
        if self.level_matches(self.NOTIFY, self._stdout_level()):
            sys.stdout.write(msg)
            sys.stdout.flush()
            self.in_progress_hanging = True
        else:
            self.in_progress_hanging = False
        self.in_progress = msg

    def end_progress(self, msg='done.'):
        assert self.in_progress, (
            "Tried to end_progress without start_progress")
        if self.stdout_level_matches(self.NOTIFY):
            if not self.in_progress_hanging:
                # Some message has been printed out since start_progress
                sys.stdout.write('...' + self.in_progress + msg + '\n')
                sys.stdout.flush()
            else:
                sys.stdout.write(msg + '\n')
                sys.stdout.flush()
        self.in_progress = None
        self.in_progress_hanging = False

    def show_progress(self):
        """If we are in a progress scope, and no log messages have been
        shown, write out another '.'"""
        if self.in_progress_hanging:
            sys.stdout.write('.')
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

    #@classmethod
    def level_for_integer(cls, level):
        levels = cls.LEVELS
        if level < 0:
            return levels[0]
        if level >= len(levels):
            return levels[-1]
        return levels[level]

    level_for_integer = classmethod(level_for_integer)

# create a silent logger just to prevent this from being undefined
# will be overridden with requested verbosity main() is called.
logger = Logger([(Logger.LEVELS[-1], sys.stdout)])

def mkdir(path):
    if not os.path.exists(path):
        logger.info('Creating %s', path)
        os.makedirs(path)
    else:
        logger.info('Directory %s already exists', path)

def copyfileordir(src, dest, symlink=True):
    if os.path.isdir(src):
        shutil.copytree(src, dest, symlink)
    else:
        shutil.copy2(src, dest)

def copyfile(src, dest, symlink=True):
    if not os.path.exists(src):
        # Some bad symlink in the src
        logger.warn('Cannot find file %s (bad symlink)', src)
        return
    if os.path.exists(dest):
        logger.debug('File %s already exists', dest)
        return
    if not os.path.exists(os.path.dirname(dest)):
        logger.info('Creating parent directories for %s', os.path.dirname(dest))
        os.makedirs(os.path.dirname(dest))
    if not os.path.islink(src):
        srcpath = os.path.abspath(src)
    else:
        srcpath = os.readlink(src)
    if symlink and hasattr(os, 'symlink') and not is_win:
        logger.info('Symlinking %s', dest)
        try:
            os.symlink(srcpath, dest)
        except (OSError, NotImplementedError):
            logger.info('Symlinking failed, copying to %s', dest)
            copyfileordir(src, dest, symlink)
    else:
        logger.info('Copying to %s', dest)
        copyfileordir(src, dest, symlink)

def writefile(dest, content, overwrite=True):
    if not os.path.exists(dest):
        logger.info('Writing %s', dest)
        f = open(dest, 'wb')
        f.write(content.encode('utf-8'))
        f.close()
        return
    else:
        f = open(dest, 'rb')
        c = f.read()
        f.close()
        if c != content.encode("utf-8"):
            if not overwrite:
                logger.notify('File %s exists with different content; not overwriting', dest)
                return
            logger.notify('Overwriting %s with new content', dest)
            f = open(dest, 'wb')
            f.write(content.encode('utf-8'))
            f.close()
        else:
            logger.info('Content %s already in place', dest)

def rmtree(dir):
    if os.path.exists(dir):
        logger.notify('Deleting tree %s', dir)
        shutil.rmtree(dir)
    else:
        logger.info('Do not need to delete %s; already gone', dir)

def make_exe(fn):
    if hasattr(os, 'chmod'):
        oldmode = os.stat(fn).st_mode & 0xFFF # 0o7777
        newmode = (oldmode | 0x16D) & 0xFFF # 0o555, 0o7777
        os.chmod(fn, newmode)
        logger.info('Changed mode of %s to %s', fn, oct(newmode))

def _find_file(filename, dirs):
    for dir in reversed(dirs):
        files = glob.glob(os.path.join(dir, filename))
        if files and os.path.isfile(files[0]):
            return True, files[0]
    return False, filename

def file_search_dirs():
    here = os.path.dirname(os.path.abspath(__file__))
    dirs = ['.', here,
            join(here, 'virtualenv_support')]
    if os.path.splitext(os.path.dirname(__file__))[0] != 'virtualenv':
        # Probably some boot script; just in case virtualenv is installed...
        try:
            import virtualenv
        except ImportError:
            pass
        else:
            dirs.append(os.path.join(os.path.dirname(virtualenv.__file__), 'virtualenv_support'))
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
        config_file = os.environ.get('VIRTUALENV_CONFIG_FILE', False)
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
        config.update(dict(self.get_config_section('virtualenv')))
        # 2. environmental variables
        config.update(dict(self.get_environ_vars()))
        # Then set the options with those values
        for key, val in config.items():
            key = key.replace('_', '-')
            if not key.startswith('--'):
                key = '--%s' % key  # only prefer long opts
            option = self.get_option(key)
            if option is not None:
                # ignore empty values
                if not val:
                    continue
                # handle multiline configs
                if option.action == 'append':
                    val = val.split()
                else:
                    option.nargs = 1
                if option.action == 'store_false':
                    val = not strtobool(val)
                elif option.action in ('store_true', 'count'):
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

    def get_environ_vars(self, prefix='VIRTUALENV_'):
        """
        Returns a generator with all environmental vars with prefix VIRTUALENV
        """
        for key, val in os.environ.items():
            if key.startswith(prefix):
                yield (key.replace(prefix, '').lower(), val)

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
        version=virtualenv_version,
        usage="%prog [OPTIONS] DEST_DIR",
        formatter=UpdatingDefaultsHelpFormatter())

    parser.add_option(
        '-v', '--verbose',
        action='count',
        dest='verbose',
        default=0,
        help="Increase verbosity.")

    parser.add_option(
        '-q', '--quiet',
        action='count',
        dest='quiet',
        default=0,
        help='Decrease verbosity.')

    parser.add_option(
        '-p', '--python',
        dest='python',
        metavar='PYTHON_EXE',
        help='The Python interpreter to use, e.g., --python=python2.5 will use the python2.5 '
        'interpreter to create the new environment.  The default is the interpreter that '
        'virtualenv was installed with (%s)' % sys.executable)

    parser.add_option(
        '--clear',
        dest='clear',
        action='store_true',
        help="Clear out the non-root install and start from scratch.")

    parser.set_defaults(system_site_packages=False)
    parser.add_option(
        '--no-site-packages',
        dest='system_site_packages',
        action='store_false',
        help="DEPRECATED. Retained only for backward compatibility. "
             "Not having access to global site-packages is now the default behavior.")

    parser.add_option(
        '--system-site-packages',
        dest='system_site_packages',
        action='store_true',
        help="Give the virtual environment access to the global site-packages.")

    parser.add_option(
        '--always-copy',
        dest='symlink',
        action='store_false',
        default=True,
        help="Always copy files rather than symlinking.")

    parser.add_option(
        '--unzip-setuptools',
        dest='unzip_setuptools',
        action='store_true',
        help="Unzip Setuptools when installing it.")

    parser.add_option(
        '--relocatable',
        dest='relocatable',
        action='store_true',
        help='Make an EXISTING virtualenv environment relocatable. '
             'This fixes up scripts and makes all .pth files relative.')

    parser.add_option(
        '--no-setuptools',
        dest='no_setuptools',
        action='store_true',
        help='Do not install setuptools (or pip) in the new virtualenv.')

    parser.add_option(
        '--no-pip',
        dest='no_pip',
        action='store_true',
        help='Do not install pip in the new virtualenv.')

    default_search_dirs = file_search_dirs()
    parser.add_option(
        '--extra-search-dir',
        dest="search_dirs",
        action="append",
        metavar='DIR',
        default=default_search_dirs,
        help="Directory to look for setuptools/pip distributions in. "
              "This option can be used multiple times.")

    parser.add_option(
        '--never-download',
        dest="never_download",
        action="store_true",
        default=True,
        help="DEPRECATED. Retained only for backward compatibility. This option has no effect. "
              "Virtualenv never downloads pip or setuptools.")

    parser.add_option(
        '--prompt',
        dest='prompt',
        help='Provides an alternative prompt prefix for this environment.')

    parser.add_option(
        '--setuptools',
        dest='setuptools',
        action='store_true',
        help="DEPRECATED. Retained only for backward compatibility. This option has no effect.")

    parser.add_option(
        '--distribute',
        dest='distribute',
        action='store_true',
        help="DEPRECATED. Retained only for backward compatibility. This option has no effect.")

    if 'extend_parser' in globals():
        extend_parser(parser)

    options, args = parser.parse_args()

    global logger

    if 'adjust_options' in globals():
        adjust_options(options, args)

    verbosity = options.verbose - options.quiet
    logger = Logger([(Logger.level_for_integer(2 - verbosity), sys.stdout)])

    if options.python and not os.environ.get('VIRTUALENV_INTERPRETER_RUNNING'):
        env = os.environ.copy()
        interpreter = resolve_interpreter(options.python)
        if interpreter == sys.executable:
            logger.warn('Already using interpreter %s' % interpreter)
        else:
            logger.notify('Running virtualenv with interpreter %s' % interpreter)
            env['VIRTUALENV_INTERPRETER_RUNNING'] = 'true'
            file = __file__
            if file.endswith('.pyc'):
                file = file[:-1]
            popen = subprocess.Popen([interpreter, file] + sys.argv[1:], env=env)
            raise SystemExit(popen.wait())

    if not args:
        print('You must provide a DEST_DIR')
        parser.print_help()
        sys.exit(2)
    if len(args) > 1:
        print('There must be only one argument: DEST_DIR (you gave %s)' % (
            ' '.join(args)))
        parser.print_help()
        sys.exit(2)

    home_dir = args[0]

    if os.environ.get('WORKING_ENV'):
        logger.fatal('ERROR: you cannot run virtualenv while in a workingenv')
        logger.fatal('Please deactivate your workingenv, then re-run this script')
        sys.exit(3)

    if 'PYTHONHOME' in os.environ:
        logger.warn('PYTHONHOME is set.  You *must* activate the virtualenv before using it')
        del os.environ['PYTHONHOME']

    if options.relocatable:
        make_environment_relocatable(home_dir)
        return

    if not options.never_download:
        logger.warn('The --never-download option is for backward compatibility only.')
        logger.warn('Setting it to false is no longer supported, and will be ignored.')

    create_environment(home_dir,
                       site_packages=options.system_site_packages,
                       clear=options.clear,
                       unzip_setuptools=options.unzip_setuptools,
                       prompt=options.prompt,
                       search_dirs=options.search_dirs,
                       never_download=True,
                       no_setuptools=options.no_setuptools,
                       no_pip=options.no_pip,
                       symlink=options.symlink)
    if 'after_install' in globals():
        after_install(options, home_dir)

def call_subprocess(cmd, show_stdout=True,
                    filter_stdout=None, cwd=None,
                    raise_on_returncode=True, extra_env=None,
                    remove_from_env=None):
    cmd_parts = []
    for part in cmd:
        if len(part) > 45:
            part = part[:20]+"..."+part[-20:]
        if ' ' in part or '\n' in part or '"' in part or "'" in part:
            part = '"%s"' % part.replace('"', '\\"')
        if hasattr(part, 'decode'):
            try:
                part = part.decode(sys.getdefaultencoding())
            except UnicodeDecodeError:
                part = part.decode(sys.getfilesystemencoding())
        cmd_parts.append(part)
    cmd_desc = ' '.join(cmd_parts)
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
            cmd, stderr=subprocess.STDOUT, stdin=None, stdout=stdout,
            cwd=cwd, env=env)
    except Exception:
        e = sys.exc_info()[1]
        logger.fatal(
            "Error %s while executing command %s" % (e, cmd_desc))
        raise
    all_output = []
    if stdout is not None:
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
        proc.communicate()
    proc.wait()
    if proc.returncode:
        if raise_on_returncode:
            if all_output:
                logger.notify('Complete output from command %s:' % cmd_desc)
                logger.notify('\n'.join(all_output) + '\n----------------------------------------')
            raise OSError(
                "Command %s failed with error code %s"
                % (cmd_desc, proc.returncode))
        else:
            logger.warn(
                "Command %s had error code %s"
                % (cmd_desc, proc.returncode))

def filter_install_output(line):
    if line.strip().startswith('running'):
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
            files = glob.glob(os.path.join(dirname, project + '-*.whl'))
            if files:
                wheels.append(os.path.abspath(files[0]))
                break
        else:
            # We're out of luck, so quit with a suitable error
            logger.fatal('Cannot find a wheel for %s' % (project,))

    return wheels

def install_wheel(project_names, py_executable, search_dirs=None):
    if search_dirs is None:
        search_dirs = file_search_dirs()

    wheels = find_wheels(['setuptools', 'pip'], search_dirs)
    pythonpath = os.pathsep.join(wheels)
    findlinks = ' '.join(search_dirs)

    cmd = [
        py_executable, '-c',
        'import sys, pip; sys.exit(pip.main(["install", "--ignore-installed"] + sys.argv[1:]))',
    ] + project_names
    logger.start_progress('Installing %s...' % (', '.join(project_names)))
    logger.indent += 2
    try:
        call_subprocess(cmd, show_stdout=False,
            extra_env = {
                'PYTHONPATH': pythonpath,
                'PIP_FIND_LINKS': findlinks,
                'PIP_USE_WHEEL': '1',
                'PIP_PRE': '1',
                'PIP_NO_INDEX': '1'
            }
        )
    finally:
        logger.indent -= 2
        logger.end_progress()

def create_environment(home_dir, site_packages=False, clear=False,
                       unzip_setuptools=False,
                       prompt=None, search_dirs=None, never_download=False,
                       no_setuptools=False, no_pip=False, symlink=True):
    """
    Creates a new environment in ``home_dir``.

    If ``site_packages`` is true, then the global ``site-packages/``
    directory will be on the path.

    If ``clear`` is true (default False) then the environment will
    first be cleared.
    """
    home_dir, lib_dir, inc_dir, bin_dir = path_locations(home_dir)

    py_executable = os.path.abspath(install_python(
        home_dir, lib_dir, inc_dir, bin_dir,
        site_packages=site_packages, clear=clear, symlink=symlink))

    install_distutils(home_dir)

    if not no_setuptools:
        to_install = ['setuptools']
        if not no_pip:
            to_install.append('pip')
        install_wheel(to_install, py_executable, search_dirs)

    install_activate(home_dir, bin_dir, prompt)

def is_executable_file(fpath):
    return os.path.isfile(fpath) and os.access(fpath, os.X_OK)

def path_locations(home_dir):
    """Return the path locations for the environment (where libraries are,
    where scripts go, etc)"""
    # XXX: We'd use distutils.sysconfig.get_python_inc/lib but its
    # prefix arg is broken: http://bugs.python.org/issue3386
    if is_win:
        # Windows has lots of problems with executables with spaces in
        # the name; this function will remove them (using the ~1
        # format):
        mkdir(home_dir)
        if ' ' in home_dir:
            import ctypes
            GetShortPathName = ctypes.windll.kernel32.GetShortPathNameW
            size = max(len(home_dir)+1, 256)
            buf = ctypes.create_unicode_buffer(size)
            try:
                u = unicode
            except NameError:
                u = str
            ret = GetShortPathName(u(home_dir), buf, size)
            if not ret:
                print('Error: the path "%s" has a space in it' % home_dir)
                print('We could not determine the short pathname for it.')
                print('Exiting.')
                sys.exit(3)
            home_dir = str(buf.value)
        lib_dir = join(home_dir, 'Lib')
        inc_dir = join(home_dir, 'Include')
        bin_dir = join(home_dir, 'Scripts')
    if is_jython:
        lib_dir = join(home_dir, 'Lib')
        inc_dir = join(home_dir, 'Include')
        bin_dir = join(home_dir, 'bin')
    elif is_pypy:
        lib_dir = home_dir
        inc_dir = join(home_dir, 'include')
        bin_dir = join(home_dir, 'bin')
    elif not is_win:
        lib_dir = join(home_dir, 'lib', py_version)
        multiarch_exec = '/usr/bin/multiarch-platform'
        if is_executable_file(multiarch_exec):
            # In Mageia (2) and Mandriva distros the include dir must be like:
            # virtualenv/include/multiarch-x86_64-linux/python2.7
            # instead of being virtualenv/include/python2.7
            p = subprocess.Popen(multiarch_exec, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            stdout, stderr = p.communicate()
            # stdout.strip is needed to remove newline character
            inc_dir = join(home_dir, 'include', stdout.strip(), py_version + abiflags)
        else:
            inc_dir = join(home_dir, 'include', py_version + abiflags)
        bin_dir = join(home_dir, 'bin')
    return home_dir, lib_dir, inc_dir, bin_dir


def change_prefix(filename, dst_prefix):
    prefixes = [sys.prefix]

    if is_darwin:
        prefixes.extend((
            os.path.join("/Library/Python", sys.version[:3], "site-packages"),
            os.path.join(sys.prefix, "Extras", "lib", "python"),
            os.path.join("~", "Library", "Python", sys.version[:3], "site-packages"),
            # Python 2.6 no-frameworks
            os.path.join("~", ".local", "lib","python", sys.version[:3], "site-packages"),
            # System Python 2.7 on OSX Mountain Lion
            os.path.join("~", "Library", "Python", sys.version[:3], "lib", "python", "site-packages")))

    if hasattr(sys, 'real_prefix'):
        prefixes.append(sys.real_prefix)
    if hasattr(sys, 'base_prefix'):
        prefixes.append(sys.base_prefix)
    prefixes = list(map(os.path.expanduser, prefixes))
    prefixes = list(map(os.path.abspath, prefixes))
    # Check longer prefixes first so we don't split in the middle of a filename
    prefixes = sorted(prefixes, key=len, reverse=True)
    filename = os.path.abspath(filename)
    for src_prefix in prefixes:
        if filename.startswith(src_prefix):
            _, relpath = filename.split(src_prefix, 1)
            if src_prefix != os.sep: # sys.prefix == "/"
                assert relpath[0] == os.sep
                relpath = relpath[1:]
            return join(dst_prefix, relpath)
    assert False, "Filename %s does not start with any of these prefixes: %s" % \
        (filename, prefixes)

def copy_required_modules(dst_prefix, symlink):
    import imp
    # If we are running under -p, we need to remove the current
    # directory from sys.path temporarily here, so that we
    # definitely get the modules from the site directory of
    # the interpreter we are running under, not the one
    # virtualenv.py is installed under (which might lead to py2/py3
    # incompatibility issues)
    _prev_sys_path = sys.path
    if os.environ.get('VIRTUALENV_INTERPRETER_RUNNING'):
        sys.path = sys.path[1:]
    try:
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
                if modname == 'readline' and sys.platform == 'darwin' and not (
                        is_pypy or filename.endswith(join('lib-dynload', 'readline.so'))):
                    dst_filename = join(dst_prefix, 'lib', 'python%s' % sys.version[:3], 'readline.so')
                elif modname == 'readline' and sys.platform == 'win32':
                    # special-case for Windows, where readline is not a
                    # standard module, though it may have been installed in
                    # site-packages by a third-party package
                    pass
                else:
                    dst_filename = change_prefix(filename, dst_prefix)
                copyfile(filename, dst_filename, symlink)
                if filename.endswith('.pyc'):
                    pyfile = filename[:-1]
                    if os.path.exists(pyfile):
                        copyfile(pyfile, dst_filename[:-1], symlink)
    finally:
        sys.path = _prev_sys_path


def subst_path(prefix_path, prefix, home_dir):
    prefix_path = os.path.normpath(prefix_path)
    prefix = os.path.normpath(prefix)
    home_dir = os.path.normpath(home_dir)
    if not prefix_path.startswith(prefix):
        logger.warn('Path not in prefix %r %r', prefix_path, prefix)
        return
    return prefix_path.replace(prefix, home_dir, 1)


def install_python(home_dir, lib_dir, inc_dir, bin_dir, site_packages, clear, symlink=True):
    """Install just the base environment, no distutils patches etc"""
    if sys.executable.startswith(bin_dir):
        print('Please use the *system* python to run this script')
        return

    if clear:
        rmtree(lib_dir)
        ## FIXME: why not delete it?
        ## Maybe it should delete everything with #!/path/to/venv/python in it
        logger.notify('Not deleting %s', bin_dir)

    if hasattr(sys, 'real_prefix'):
        logger.notify('Using real prefix %r' % sys.real_prefix)
        prefix = sys.real_prefix
    elif hasattr(sys, 'base_prefix'):
        logger.notify('Using base prefix %r' % sys.base_prefix)
        prefix = sys.base_prefix
    else:
        prefix = sys.prefix
    mkdir(lib_dir)
    fix_lib64(lib_dir, symlink)
    stdlib_dirs = [os.path.dirname(os.__file__)]
    if is_win:
        stdlib_dirs.append(join(os.path.dirname(stdlib_dirs[0]), 'DLLs'))
    elif is_darwin:
        stdlib_dirs.append(join(stdlib_dirs[0], 'site-packages'))
    if hasattr(os, 'symlink'):
        logger.info('Symlinking Python bootstrap modules')
    else:
        logger.info('Copying Python bootstrap modules')
    logger.indent += 2
    try:
        # copy required files...
        for stdlib_dir in stdlib_dirs:
            if not os.path.isdir(stdlib_dir):
                continue
            for fn in os.listdir(stdlib_dir):
                bn = os.path.splitext(fn)[0]
                if fn != 'site-packages' and bn in REQUIRED_FILES:
                    copyfile(join(stdlib_dir, fn), join(lib_dir, fn), symlink)
        # ...and modules
        copy_required_modules(home_dir, symlink)
    finally:
        logger.indent -= 2
    mkdir(join(lib_dir, 'site-packages'))
    import site
    site_filename = site.__file__
    if site_filename.endswith('.pyc'):
        site_filename = site_filename[:-1]
    elif site_filename.endswith('$py.class'):
        site_filename = site_filename.replace('$py.class', '.py')
    site_filename_dst = change_prefix(site_filename, home_dir)
    site_dir = os.path.dirname(site_filename_dst)
    writefile(site_filename_dst, SITE_PY)
    writefile(join(site_dir, 'orig-prefix.txt'), prefix)
    site_packages_filename = join(site_dir, 'no-global-site-packages.txt')
    if not site_packages:
        writefile(site_packages_filename, '')

    if is_pypy or is_win:
        stdinc_dir = join(prefix, 'include')
    else:
        stdinc_dir = join(prefix, 'include', py_version + abiflags)
    if os.path.exists(stdinc_dir):
        copyfile(stdinc_dir, inc_dir, symlink)
    else:
        logger.debug('No include dir %s' % stdinc_dir)

    platinc_dir = distutils.sysconfig.get_python_inc(plat_specific=1)
    if platinc_dir != stdinc_dir:
        platinc_dest = distutils.sysconfig.get_python_inc(
            plat_specific=1, prefix=home_dir)
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
            exec_dir = join(sys.exec_prefix, 'lib')
        elif is_jython:
            exec_dir = join(sys.exec_prefix, 'Lib')
        else:
            exec_dir = join(sys.exec_prefix, 'lib', py_version)
        for fn in os.listdir(exec_dir):
            copyfile(join(exec_dir, fn), join(lib_dir, fn), symlink)

    if is_jython:
        # Jython has either jython-dev.jar and javalib/ dir, or just
        # jython.jar
        for name in 'jython-dev.jar', 'javalib', 'jython.jar':
            src = join(prefix, name)
            if os.path.exists(src):
                copyfile(src, join(home_dir, name), symlink)
        # XXX: registry should always exist after Jython 2.5rc1
        src = join(prefix, 'registry')
        if os.path.exists(src):
            copyfile(src, join(home_dir, 'registry'), symlink=False)
        copyfile(join(prefix, 'cachedir'), join(home_dir, 'cachedir'),
                 symlink=False)

    mkdir(bin_dir)
    py_executable = join(bin_dir, os.path.basename(sys.executable))
    if 'Python.framework' in prefix:
        # OS X framework builds cause validation to break
        # https://github.com/pypa/virtualenv/issues/322
        if os.environ.get('__PYVENV_LAUNCHER__'):
            del os.environ["__PYVENV_LAUNCHER__"]
        if re.search(r'/Python(?:-32|-64)*$', py_executable):
            # The name of the python executable is not quite what
            # we want, rename it.
            py_executable = os.path.join(
                    os.path.dirname(py_executable), 'python')

    logger.notify('New %s executable in %s', expected_exe, py_executable)
    pcbuild_dir = os.path.dirname(sys.executable)
    pyd_pth = os.path.join(lib_dir, 'site-packages', 'virtualenv_builddir_pyd.pth')
    if is_win and os.path.exists(os.path.join(pcbuild_dir, 'build.bat')):
        logger.notify('Detected python running from build directory %s', pcbuild_dir)
        logger.notify('Writing .pth file linking to build directory for *.pyd files')
        writefile(pyd_pth, pcbuild_dir)
    else:
        pcbuild_dir = None
        if os.path.exists(pyd_pth):
            logger.info('Deleting %s (not Windows env or not build directory python)' % pyd_pth)
            os.unlink(pyd_pth)

    if sys.executable != py_executable:
        ## FIXME: could I just hard link?
        executable = sys.executable
        shutil.copyfile(executable, py_executable)
        make_exe(py_executable)
        if is_win or is_cygwin:
            pythonw = os.path.join(os.path.dirname(sys.executable), 'pythonw.exe')
            if os.path.exists(pythonw):
                logger.info('Also created pythonw.exe')
                shutil.copyfile(pythonw, os.path.join(os.path.dirname(py_executable), 'pythonw.exe'))
            python_d = os.path.join(os.path.dirname(sys.executable), 'python_d.exe')
            python_d_dest = os.path.join(os.path.dirname(py_executable), 'python_d.exe')
            if os.path.exists(python_d):
                logger.info('Also created python_d.exe')
                shutil.copyfile(python_d, python_d_dest)
            elif os.path.exists(python_d_dest):
                logger.info('Removed python_d.exe as it is no longer at the source')
                os.unlink(python_d_dest)
            # we need to copy the DLL to enforce that windows will load the correct one.
            # may not exist if we are cygwin.
            py_executable_dll = 'python%s%s.dll' % (
                sys.version_info[0], sys.version_info[1])
            py_executable_dll_d = 'python%s%s_d.dll' % (
                sys.version_info[0], sys.version_info[1])
            pythondll = os.path.join(os.path.dirname(sys.executable), py_executable_dll)
            pythondll_d = os.path.join(os.path.dirname(sys.executable), py_executable_dll_d)
            pythondll_d_dest = os.path.join(os.path.dirname(py_executable), py_executable_dll_d)
            if os.path.exists(pythondll):
                logger.info('Also created %s' % py_executable_dll)
                shutil.copyfile(pythondll, os.path.join(os.path.dirname(py_executable), py_executable_dll))
            if os.path.exists(pythondll_d):
                logger.info('Also created %s' % py_executable_dll_d)
                shutil.copyfile(pythondll_d, pythondll_d_dest)
            elif os.path.exists(pythondll_d_dest):
                logger.info('Removed %s as the source does not exist' % pythondll_d_dest)
                os.unlink(pythondll_d_dest)
        if is_pypy:
            # make a symlink python --> pypy-c
            python_executable = os.path.join(os.path.dirname(py_executable), 'python')
            if sys.platform in ('win32', 'cygwin'):
                python_executable += '.exe'
            logger.info('Also created executable %s' % python_executable)
            copyfile(py_executable, python_executable, symlink)

            if is_win:
                for name in ['libexpat.dll', 'libpypy.dll', 'libpypy-c.dll',
                            'libeay32.dll', 'ssleay32.dll', 'sqlite3.dll',
                            'tcl85.dll', 'tk85.dll']:
                    src = join(prefix, name)
                    if os.path.exists(src):
                        copyfile(src, join(bin_dir, name), symlink)

                for d in sys.path:
                    if d.endswith('lib_pypy'):
                        break
                else:
                    logger.fatal('Could not find lib_pypy in sys.path')
                    raise SystemExit(3)
                logger.info('Copying lib_pypy')
                copyfile(d, os.path.join(home_dir, 'lib_pypy'), symlink)

    if os.path.splitext(os.path.basename(py_executable))[0] != expected_exe:
        secondary_exe = os.path.join(os.path.dirname(py_executable),
                                     expected_exe)
        py_executable_ext = os.path.splitext(py_executable)[1]
        if py_executable_ext.lower() == '.exe':
            # python2.4 gives an extension of '.4' :P
            secondary_exe += py_executable_ext
        if os.path.exists(secondary_exe):
            logger.warn('Not overwriting existing %s script %s (you must use %s)'
                        % (expected_exe, secondary_exe, py_executable))
        else:
            logger.notify('Also creating executable in %s' % secondary_exe)
            shutil.copyfile(sys.executable, secondary_exe)
            make_exe(secondary_exe)

    if '.framework' in prefix:
        if 'Python.framework' in prefix:
            logger.debug('MacOSX Python framework detected')
            # Make sure we use the embedded interpreter inside
            # the framework, even if sys.executable points to
            # the stub executable in ${sys.prefix}/bin
            # See http://groups.google.com/group/python-virtualenv/
            #                              browse_thread/thread/17cab2f85da75951
            original_python = os.path.join(
                prefix, 'Resources/Python.app/Contents/MacOS/Python')
        if 'EPD' in prefix:
            logger.debug('EPD framework detected')
            original_python = os.path.join(prefix, 'bin/python')
        shutil.copy(original_python, py_executable)

        # Copy the framework's dylib into the virtual
        # environment
        virtual_lib = os.path.join(home_dir, '.Python')

        if os.path.exists(virtual_lib):
            os.unlink(virtual_lib)
        copyfile(
            os.path.join(prefix, 'Python'),
            virtual_lib,
            symlink)

        # And then change the install_name of the copied python executable
        try:
            mach_o_change(py_executable,
                          os.path.join(prefix, 'Python'),
                          '@executable_path/../.Python')
        except:
            e = sys.exc_info()[1]
            logger.warn("Could not call mach_o_change: %s. "
                        "Trying to call install_name_tool instead." % e)
            try:
                call_subprocess(
                    ["install_name_tool", "-change",
                     os.path.join(prefix, 'Python'),
                     '@executable_path/../.Python',
                     py_executable])
            except:
                logger.fatal("Could not call install_name_tool -- you must "
                             "have Apple's development tools installed")
                raise

    if not is_win:
        # Ensure that 'python', 'pythonX' and 'pythonX.Y' all exist
        py_exe_version_major = 'python%s' % sys.version_info[0]
        py_exe_version_major_minor = 'python%s.%s' % (
            sys.version_info[0], sys.version_info[1])
        py_exe_no_version = 'python'
        required_symlinks = [ py_exe_no_version, py_exe_version_major,
                         py_exe_version_major_minor ]

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

    if is_win and ' ' in py_executable:
        # There's a bug with subprocess on Windows when using a first
        # argument that has a space in it.  Instead we have to quote
        # the value:
        py_executable = '"%s"' % py_executable
    # NOTE: keep this check as one line, cmd.exe doesn't cope with line breaks
    cmd = [py_executable, '-c', 'import sys;out=sys.stdout;'
        'getattr(out, "buffer", out).write(sys.prefix.encode("utf-8"))']
    logger.info('Testing executable with %s %s "%s"' % tuple(cmd))
    try:
        proc = subprocess.Popen(cmd,
                            stdout=subprocess.PIPE)
        proc_stdout, proc_stderr = proc.communicate()
    except OSError:
        e = sys.exc_info()[1]
        if e.errno == errno.EACCES:
            logger.fatal('ERROR: The executable %s could not be run: %s' % (py_executable, e))
            sys.exit(100)
        else:
            raise e

    proc_stdout = proc_stdout.strip().decode("utf-8")
    proc_stdout = os.path.normcase(os.path.abspath(proc_stdout))
    norm_home_dir = os.path.normcase(os.path.abspath(home_dir))
    if hasattr(norm_home_dir, 'decode'):
        norm_home_dir = norm_home_dir.decode(sys.getfilesystemencoding())
    if proc_stdout != norm_home_dir:
        logger.fatal(
            'ERROR: The executable %s is not functioning' % py_executable)
        logger.fatal(
            'ERROR: It thinks sys.prefix is %r (should be %r)'
            % (proc_stdout, norm_home_dir))
        logger.fatal(
            'ERROR: virtualenv is not compatible with this system or executable')
        if is_win:
            logger.fatal(
                'Note: some Windows users have reported this error when they '
                'installed Python for "Only this user" or have multiple '
                'versions of Python installed. Copying the appropriate '
                'PythonXX.dll to the virtualenv Scripts/ directory may fix '
                'this problem.')
        sys.exit(100)
    else:
        logger.info('Got sys.prefix result: %r' % proc_stdout)

    pydistutils = os.path.expanduser('~/.pydistutils.cfg')
    if os.path.exists(pydistutils):
        logger.notify('Please make sure you remove any previous custom paths from '
                      'your %s file.' % pydistutils)
    ## FIXME: really this should be calculated earlier

    fix_local_scheme(home_dir, symlink)

    if site_packages:
        if os.path.exists(site_packages_filename):
            logger.info('Deleting %s' % site_packages_filename)
            os.unlink(site_packages_filename)

    return py_executable


def install_activate(home_dir, bin_dir, prompt=None):
    home_dir = os.path.abspath(home_dir)
    if is_win or is_jython and os._name == 'nt':
        files = {
            'activate.bat': ACTIVATE_BAT,
            'deactivate.bat': DEACTIVATE_BAT,
            'activate.ps1': ACTIVATE_PS,
        }

        # MSYS needs paths of the form /c/path/to/file
        drive, tail = os.path.splitdrive(home_dir.replace(os.sep, '/'))
        home_dir_msys = (drive and "/%s%s" or "%s%s") % (drive[:1], tail)

        # Run-time conditional enables (basic) Cygwin compatibility
        home_dir_sh = ("""$(if [ "$OSTYPE" "==" "cygwin" ]; then cygpath -u '%s'; else echo '%s'; fi;)""" %
                       (home_dir, home_dir_msys))
        files['activate'] = ACTIVATE_SH.replace('__VIRTUAL_ENV__', home_dir_sh)

    else:
        files = {'activate': ACTIVATE_SH}

        # suppling activate.fish in addition to, not instead of, the
        # bash script support.
        files['activate.fish'] = ACTIVATE_FISH

        # same for csh/tcsh support...
        files['activate.csh'] = ACTIVATE_CSH

    files['activate_this.py'] = ACTIVATE_THIS
    if hasattr(home_dir, 'decode'):
        home_dir = home_dir.decode(sys.getfilesystemencoding())
    vname = os.path.basename(home_dir)
    for name, content in files.items():
        content = content.replace('__VIRTUAL_PROMPT__', prompt or '')
        content = content.replace('__VIRTUAL_WINPROMPT__', prompt or '(%s)' % vname)
        content = content.replace('__VIRTUAL_ENV__', home_dir)
        content = content.replace('__VIRTUAL_NAME__', vname)
        content = content.replace('__BIN_NAME__', os.path.basename(bin_dir))
        writefile(os.path.join(bin_dir, name), content)

def install_distutils(home_dir):
    distutils_path = change_prefix(distutils.__path__[0], home_dir)
    mkdir(distutils_path)
    ## FIXME: maybe this prefix setting should only be put in place if
    ## there's a local distutils.cfg with a prefix setting?
    home_dir = os.path.abspath(home_dir)
    ## FIXME: this is breaking things, removing for now:
    #distutils_cfg = DISTUTILS_CFG + "\n[install]\nprefix=%s\n" % home_dir
    writefile(os.path.join(distutils_path, '__init__.py'), DISTUTILS_INIT)
    writefile(os.path.join(distutils_path, 'distutils.cfg'), DISTUTILS_CFG, overwrite=False)

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
        if sysconfig._get_default_scheme() == 'posix_local':
            local_path = os.path.join(home_dir, 'local')
            if not os.path.exists(local_path):
                os.mkdir(local_path)
                for subdir_name in os.listdir(home_dir):
                    if subdir_name == 'local':
                        continue
                    copyfile(os.path.abspath(os.path.join(home_dir, subdir_name)), \
                                                            os.path.join(local_path, subdir_name), symlink)

def fix_lib64(lib_dir, symlink=True):
    """
    Some platforms (particularly Gentoo on x64) put things in lib64/pythonX.Y
    instead of lib/pythonX.Y.  If this is such a platform we'll just create a
    symlink so lib64 points to lib
    """
    if [p for p in distutils.sysconfig.get_config_vars().values()
        if isinstance(p, basestring) and 'lib64' in p]:
        # PyPy's library path scheme is not affected by this.
        # Return early or we will die on the following assert.
        if is_pypy:
            logger.debug('PyPy detected, skipping lib64 symlinking')
            return

        logger.debug('This system uses lib64; symlinking lib64 to lib')

        assert os.path.basename(lib_dir) == 'python%s' % sys.version[:3], (
            "Unexpected python lib dir: %r" % lib_dir)
        lib_parent = os.path.dirname(lib_dir)
        top_level = os.path.dirname(lib_parent)
        lib_dir = os.path.join(top_level, 'lib')
        lib64_link = os.path.join(top_level, 'lib64')
        assert os.path.basename(lib_parent) == 'lib', (
            "Unexpected parent dir: %r" % lib_parent)
        if os.path.lexists(lib64_link):
            return
        if symlink:
            os.symlink('lib', lib64_link)
        else:
            copyfile('lib', lib64_link)

def resolve_interpreter(exe):
    """
    If the executable given isn't an absolute path, search $PATH for the interpreter
    """
    # If the "executable" is a version number, get the installed executable for
    # that version
    python_versions = get_installed_pythons()
    if exe in python_versions:
        exe = python_versions[exe]

    if os.path.abspath(exe) != exe:
        paths = os.environ.get('PATH', '').split(os.pathsep)
        for path in paths:
            if os.path.exists(os.path.join(path, exe)):
                exe = os.path.join(path, exe)
                break
    if not os.path.exists(exe):
        logger.fatal('The executable %s (from --python=%s) does not exist' % (exe, exe))
        raise SystemExit(3)
    if not is_executable(exe):
        logger.fatal('The executable %s (from --python=%s) is not executable' % (exe, exe))
        raise SystemExit(3)
    return exe

def is_executable(exe):
    """Checks a file is executable"""
    return os.access(exe, os.X_OK)

############################################################
## Relocating the environment:

def make_environment_relocatable(home_dir):
    """
    Makes the already-existing environment use relative paths, and takes out
    the #!-based environment selection in scripts.
    """
    home_dir, lib_dir, inc_dir, bin_dir = path_locations(home_dir)
    activate_this = os.path.join(bin_dir, 'activate_this.py')
    if not os.path.exists(activate_this):
        logger.fatal(
            'The environment doesn\'t have a file %s -- please re-run virtualenv '
            'on this environment to update it' % activate_this)
    fixup_scripts(home_dir, bin_dir)
    fixup_pth_and_egg_link(home_dir)
    ## FIXME: need to fix up distutils.cfg

OK_ABS_SCRIPTS = ['python', 'python%s' % sys.version[:3],
                  'activate', 'activate.bat', 'activate_this.py',
                  'activate.fish', 'activate.csh']

def fixup_scripts(home_dir, bin_dir):
    if is_win:
        new_shebang_args = (
            '%s /c' % os.path.normcase(os.environ.get('COMSPEC', 'cmd.exe')),
            '', '.exe')
    else:
        new_shebang_args = ('/usr/bin/env', sys.version[:3], '')

    # This is what we expect at the top of scripts:
    shebang = '#!%s' % os.path.normcase(os.path.join(
        os.path.abspath(bin_dir), 'python%s' % new_shebang_args[2]))
    # This is what we'll put:
    new_shebang = '#!%s python%s%s' % new_shebang_args

    for filename in os.listdir(bin_dir):
        filename = os.path.join(bin_dir, filename)
        if not os.path.isfile(filename):
            # ignore subdirs, e.g. .svn ones.
            continue
        f = open(filename, 'rb')
        try:
            try:
                lines = f.read().decode('utf-8').splitlines()
            except UnicodeDecodeError:
                # This is probably a binary program instead
                # of a script, so just ignore it.
                continue
        finally:
            f.close()
        if not lines:
            logger.warn('Script %s is an empty file' % filename)
            continue

        old_shebang = lines[0].strip()
        old_shebang = old_shebang[0:2] + os.path.normcase(old_shebang[2:])

        if not old_shebang.startswith(shebang):
            if os.path.basename(filename) in OK_ABS_SCRIPTS:
                logger.debug('Cannot make script %s relative' % filename)
            elif lines[0].strip() == new_shebang:
                logger.info('Script %s has already been made relative' % filename)
            else:
                logger.warn('Script %s cannot be made relative (it\'s not a normal script that starts with %s)'
                            % (filename, shebang))
            continue
        logger.notify('Making script %s relative' % filename)
        script = relative_script([new_shebang] + lines[1:])
        f = open(filename, 'wb')
        f.write('\n'.join(script).encode('utf-8'))
        f.close()

def relative_script(lines):
    "Return a script that'll work in a relocatable environment."
    activate = "import os; activate_this=os.path.join(os.path.dirname(os.path.realpath(__file__)), 'activate_this.py'); exec(compile(open(activate_this).read(), activate_this, 'exec'), dict(__file__=activate_this)); del os, activate_this"
    # Find the last future statement in the script. If we insert the activation
    # line before a future statement, Python will raise a SyntaxError.
    activate_at = None
    for idx, line in reversed(list(enumerate(lines))):
        if line.split()[:3] == ['from', '__future__', 'import']:
            activate_at = idx + 1
            break
    if activate_at is None:
        # Activate after the shebang.
        activate_at = 1
    return lines[:activate_at] + ['', activate, ''] + lines[activate_at:]

def fixup_pth_and_egg_link(home_dir, sys_path=None):
    """Makes .pth and .egg-link files use relative paths"""
    home_dir = os.path.normcase(os.path.abspath(home_dir))
    if sys_path is None:
        sys_path = sys.path
    for path in sys_path:
        if not path:
            path = '.'
        if not os.path.isdir(path):
            continue
        path = os.path.normcase(os.path.abspath(path))
        if not path.startswith(home_dir):
            logger.debug('Skipping system (non-environment) directory %s' % path)
            continue
        for filename in os.listdir(path):
            filename = os.path.join(path, filename)
            if filename.endswith('.pth'):
                if not os.access(filename, os.W_OK):
                    logger.warn('Cannot write .pth file %s, skipping' % filename)
                else:
                    fixup_pth_file(filename)
            if filename.endswith('.egg-link'):
                if not os.access(filename, os.W_OK):
                    logger.warn('Cannot write .egg-link file %s, skipping' % filename)
                else:
                    fixup_egg_link(filename)

def fixup_pth_file(filename):
    lines = []
    prev_lines = []
    f = open(filename)
    prev_lines = f.readlines()
    f.close()
    for line in prev_lines:
        line = line.strip()
        if (not line or line.startswith('#') or line.startswith('import ')
            or os.path.abspath(line) != line):
            lines.append(line)
        else:
            new_value = make_relative_path(filename, line)
            if line != new_value:
                logger.debug('Rewriting path %s as %s (in %s)' % (line, new_value, filename))
            lines.append(new_value)
    if lines == prev_lines:
        logger.info('No changes to .pth file %s' % filename)
        return
    logger.notify('Making paths in .pth file %s relative' % filename)
    f = open(filename, 'w')
    f.write('\n'.join(lines) + '\n')
    f.close()

def fixup_egg_link(filename):
    f = open(filename)
    link = f.readline().strip()
    f.close()
    if os.path.abspath(link) != link:
        logger.debug('Link in %s already relative' % filename)
        return
    new_link = make_relative_path(filename, link)
    logger.notify('Rewriting link %s in %s as %s' % (link, filename, new_link))
    f = open(filename, 'w')
    f.write(new_link)
    f.close()

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
    full_parts = ['..']*len(source_parts) + dest_parts
    if not dest_is_directory:
        full_parts.append(dest_filename)
    if not full_parts:
        # Special case for the current directory (otherwise it'd be '')
        return './'
    return os.path.sep.join(full_parts)



############################################################
## Bootstrap script creation:

def create_bootstrap_script(extra_text, python_version=''):
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
    if filename.endswith('.pyc'):
        filename = filename[:-1]
    f = codecs.open(filename, 'r', encoding='utf-8')
    content = f.read()
    f.close()
    py_exe = 'python%s' % python_version
    content = (('#!/usr/bin/env %s\n' % py_exe)
               + '## WARNING: This file is generated\n'
               + content)
    return content.replace('##EXT' 'END##', extra_text)

##EXTEND##

def convert(s):
    b = base64.b64decode(s.encode('ascii'))
    return zlib.decompress(b).decode('utf-8')

##file site.py
SITE_PY = convert("""
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
""")

##file activate.sh
ACTIVATE_SH = convert("""
eJytVVFvokAQfudXTLEPtTlLeo9tvMSmJpq02hSvl7u2wRUG2QR2DSxSe7n/frOACEVNLlceRHa+
nfl25pvZDswCnoDPQ4QoTRQsENIEPci4CsBMZBq7CAsuLOYqvmYKTTj3YxnBgiXBudGBjUzBZUJI
BXEqgCvweIyuCjeG4eF2F5x14bcB9KQiQQWrjSddI1/oQIx6SYYeoFjzWIoIhYI1izlbhJjkKO7D
M/QEmKfO9O7WeRo/zr4P7pyHwWxkwitcgwpQ5Ej96OX+PmiFwLeVjFUOrNYKaq1Nud3nR2n8nI2m
k9H0friPTGVsUdptaxGrTEfpNVFEskxpXtUkkCkl1UNF9cgLBkx48J4EXyALuBtAwNYIjF5kcmUU
abMKmMq1ULoiRbgsDEkTSsKSGFCJ6Z8vY/2xYiSacmtyAfCDdCNTVZoVF8vSTQOoEwSnOrngBkws
MYGMBMg8/bMBLSYKS7pYEXP0PqT+ZmBT0Xuy+Pplj5yn4aM9nk72JD8/Wi+Gr98sD9eWSMOwkapD
BbUv91XSvmyVkICt2tmXR4tWmrcUCsjWOpw87YidEC8i0gdTSOFhouJUNxR+4NYBG0MftoCTD9F7
2rTtxG3oPwY1b2HncYwhrlmj6Wq924xtGDWqfdNxap+OYxplEurnMVo9RWks+rH8qKEtx7kZT5zJ
4H7oOFclrN6uFe+d+nW2aIUsSgs/42EIPuOhXq+jEo3S6tX6w2ilNkDnIpHCWdEQhFgwj9pkk7FN
l/y5eQvRSIQ5+TrL05lewxWpt/Lbhes5cJF3mLET1MGhcKCF+40tNWnUulxrpojwDo2sObdje3Bz
N3QeHqf3D7OjEXMVV8LN3ZlvuzoWHqiUcNKHtwNd0IbvPGKYYM31nPKCgkUILw3KL+Y8l7aO1ArS
Ad37nIU0fCj5NE5gQCuC5sOSu+UdI2NeXg/lFkQIlFpdWVaWZRfvqGiirC9o6liJ9FXGYrSY9mI1
D/Ncozgn13vJvsznr7DnkJWXsyMH7e42ljdJ+aqNDF1bFnKWFLdj31xtaJYK6EXFgqmV/ymD/ROG
+n8O9H8f5vsGOWXsL1+1k3g=
""")

##file activate.fish
ACTIVATE_FISH = convert("""
eJydVW2P2jgQ/s6vmAZQoVpA9/WkqqJaTou0u6x2uZVOVWWZZEKsS+yc7UDpr+84bziQbauLxEvs
eXnsZ56ZIWwTYSAWKUJWGAs7hMJgBEdhEwiMKnSIsBNywUMrDtziPBYmCeBDrFUG7v8HmCTW5n8u
Fu7NJJim81Bl08EQTqqAkEupLOhCgrAQCY2hTU+DQVxIiqgkRNiEBphFEKy+kd1BaFvwFOUBuIxA
oy20BKtAKp3xFMo0QNtCK5mhtMEA6BmSpUELKo38TThwLfguRVNaiRgs0llnEoIR29zfstf18/bv
5T17Wm7vAiiN3ONCzfbfwC3DtWXXDqHfAGX0q6z/bO82j3ebh1VwnbrduwTQbvwcRtesAfMGor/W
L3fs6Xnz8LRlm9fV8/P61sM0LDNwCZjl9gSpCokJRzpryGQ5t8kNGFUt51QjOZGu0Mj35FlYlXEr
yC09EVOp4lEXfF84Lz1qbhBsgl59vDedXI3rTV03xipduSgt9kLytI3XmBp3aV6MPoMQGNUU62T6
uQdeefTy1Hfj10zVHg2pq8fXDoHBiOv94csfXwN49xECqWREy7pwukKfvxdMY2j23vXDPuuxxeE+
JOdCOhxCE3N44B1ZeSLuZh8Mmkr2wEPAmPfKWHA2uxIRjEopdbQYjDz3BWOf14/scfmwoki1eQvX
ExBdF60Mqh+Y/QcX4uiH4Amwzx79KOVFtbL63sXJbtcvy8/3q5rupmO5CnE91wBviQAhjUUegYpL
vVEbpLt2/W+PklRgq5Ku6mp+rpMhhCo/lXthQTxJ2ysO4Ka0ad97S7VT/n6YXus6fzk3fLnBZW5C
KDC6gSO62QDqgFqLCCtPmjegjnLeAdArtSE8VYGbAJ/aLb+vnQutFhk768E9uRbSxhCMzdgEveYw
IZ5ZqFKl6+kz7UR4U+buqQZXu9SIujrAfD7f0FXpozB4Q0gwp31H9mVTZGGC4b871/wm7lvyDLu1
FUyvTj/yvD66k3UPTs08x1AQQaGziOl0S1qRkPG9COtBTSTWM9NzQ4R64B+Px/l3tDzCgxv5C6Ni
e+QaF9xFWrxx0V/G5uvYQOdiZzvYpQUVQSIsTr1TTghI33GnPbTA7/GCqcE3oE3GZurq4HeQXQD6
32XS1ITj/qLjN72ob0hc5C9bzw8MhfmL
""")

##file activate.csh
ACTIVATE_CSH = convert("""
eJx9VG1P2zAQ/u5fcYQKNgTNPtN1WxlIQ4KCUEGaxuQ6yYVYSuzKdhqVX7+zk3bpy5YPUXL3PPfc
ne98DLNCWshliVDV1kGCUFvMoJGugMjq2qQIiVSxSJ1cCofD1BYRnOVGV0CfZ0N2DD91DalQSjsw
tQLpIJMGU1euvPe7QeJlkKzgWixlhnAt4aoUVsLnLBiy5NtbJWQ5THX1ZciYKKWwkOFaE04dUm6D
r/zh7pq/3D7Nnid3/HEy+wFHY/gEJydg0aFaQrBFgz1c5DG1IhTs+UZgsBC2GMFBlaeH+8dZXwcW
VPvCjXdlAvCfQsE7al0+07XjZvrSCUevR5dnkVeKlFYZmUztG4BdzL2u9KyLVabTU0bdfg7a0hgs
cSmUg6UwUiQl2iHrcbcVGNvPCiLOe7+cRwG13z9qRGgx2z6DHjfm/Op2yqeT+xvOLzs0PTKHDz2V
tkckFHoQfQRXoGJAj9el0FyJCmEMhzgMS4sB7KPOE2ExoLcSieYwDvR+cP8cg11gKkVJc2wRcm1g
QhYFlXiTaTfO2ki0fQoiFM4tLuO4aZrhOzqR4dIPcWx17hphMBY+Srwh7RTyN83XOWkcSPh1Pg/k
TXX/jbJTbMtUmcxZ+/bbqOsy82suFQg/BhdSOTRhMNBHlUarCpU7JzBhmkKmRejKOQzayQe6MWoa
n1wqWmuh6LZAaHxcdeqIlVLhIBJdO9/kbl0It2oEXQj+eGjJOuvOIR/YGRqvFhttUB2XTvLXYN2H
37CBdbW2W7j2r2+VsCn0doVWcFG1/4y1VwBjfwAyoZhD
""")

##file activate.bat
ACTIVATE_BAT = convert("""
eJx9UdEKgjAUfW6wfxjiIH+hEDKUFHSKLCMI7kNOEkIf9P9pTJ3OLJ/03HPPPed4Es9XS9qqwqgT
PbGKKOdXL4aAFS7A4gvAwgijuiKlqOpGlATS2NeMLE+TjJM9RkQ+SmqAXLrBo1LLIeLdiWlD6jZt
r7VNubWkndkXaxg5GO3UaOOKS6drO3luDDiO5my3iA0YAKGzPRV1ack8cOdhysI0CYzIPzjSiH5X
0QcvC8Lfaj0emsVKYF2rhL5L3fCkVjV76kShi59NHwDniAHzkgDgqBcwOgTMx+gDQQqXCw==
""")

##file deactivate.bat
DEACTIVATE_BAT = convert("""
eJxzSE3OyFfIT0vj4ipOLVEI8wwKCXX0iXf1C7Pl4spMU0hJTcvMS01RiPf3cYmHyQYE+fsGhCho
cCkAAUibEkTEVhWLMlUlLk6QGixStlyaeCyJDPHw9/Pw93VFsQguim4ZXAJoIUw5DhX47XUM8UCx
EchHtwsohN1bILUgw61c/Vy4AJYPYm4=
""")

##file activate.ps1
ACTIVATE_PS = convert("""
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
rKQDxR6N/rffXv+lROXet/9Q+l9I4D1U
""")

##file distutils-init.py
DISTUTILS_INIT = convert("""
eJytV1uL4zYUfvevOE0ottuMW9q3gVDa3aUMXXbLMlDKMBiNrSTqOJKRlMxkf33PkXyRbGe7Dw2E
UXTu37lpxLFV2oIyifAncxmOL0xLIfcG+gv80x9VW6maw7o/CANSWWBwFtqeWMPlGY6qPjV8A0bB
C4eKSTgZ5LRgFeyErMEeOBhbN+Ipgeizhjtnhkn7DdyjuNLPoCS0l/ayQTG0djwZC08cLXozeMss
aG5EzQ0IScpnWtHSTXuxByV/QCmxE7y+eS0uxWeoheaVVfqSJHiU7Mhhi6gULbOHorshkrEnKxpT
0n3A8Y8SMpuwZx6aoix3ouFlmW8gHRSkeSJ2g7hU+kiHLDaQw3bmRDaTGfTnty7gPm0FHbIBg9U9
oh1kZzAFLaue2R6htPCtAda2nGlDSUJ4PZBgCJBGVcwKTAMz/vJiLD+Oin5Z5QlvDPdulC6EsiyE
NFzb7McNTKJzbJqzphx92VKRFY1idenzmq3K0emRcbWBD0ryqc4NZGmKOOOX9Pz5x+/l27tP797c
f/z0d+4NruGNai8uAM0bfsYaw8itFk8ny41jsfpyO+BWlpqfhcG4yxLdi/0tQqoT4a8Vby382mt8
p7XSo7aWGdPBc+b6utaBmCQ7rQKQoWtAuthQCiold2KfJIPTT8xwg9blPumc+YDZC/wYGdAyHpJk
vUbHbHWAp5No6pK/WhhLEWrFjUwtPEv1Agf8YmnsuXUQYkeZoHm8ogP16gt2uHoxcEMdf2C6pmbw
hUMsWGhanboh4IzzmsIpWs134jVPqD/c74bZHdY69UKKSn/+KfVhxLgUlToemayLMYQOqfEC61bh
cbhwaqoGUzIyZRFHPmau5juaWqwRn3mpWmoEA5nhzS5gog/5jbcFQqOZvmBasZtwYlG93k5GEiyw
buHhMWLjDarEGpMGB2LFs5nIJkhp/nUmZneFaRth++lieJtHepIvKgx6PJqIlD9X2j6pG1i9x3pZ
5bHuCPFiirGHeO7McvoXkz786GaKVzC9DSpnOxJdc4xm6NSVq7lNEnKdVlnpu9BNYoKX2Iq3wvgh
gGEUM66kK6j4NiyoneuPLSwaCWDxczgaolEWpiMyDVDb7dNuLAbriL8ig8mmeju31oNvQdpnvEPC
1vAXbWacGRVrGt/uXN/gU0CDDwgooKRrHfTBb1/s9lYZ8ZqOBU0yLvpuP6+K9hLFsvIjeNhBi0KL
MlOuWRn3FRwx5oHXjl0YImUx0+gLzjGchrgzca026ETmYJzPD+IpuKzNi8AFn048Thd63OdD86M6
84zE8yQm0VqXdbbgvub2pKVnS76icBGdeTHHXTKspUmr4NYo/furFLKiMdQzFjHJNcdAnMhltBJK
0/IKX3DVFqvPJ2dLE7bDBkH0l/PJ29074+F0CsGYOxsb7U3myTUncYfXqnLLfa6sJybX4g+hmcjO
kMRBfA1JellfRRKJcyRpxdS4rIl6FdmQCWjo/o9Qz7yKffoP4JHjOvABcRn4CZIT2RH4jnxmfpVG
qgLaAvQBNfuO6X0/Ux02nb4FKx3vgP+XnkX0QW9pLy/NsXgdN24dD3LxO2Nwil7Zlc1dqtP3d7/h
kzp1/+7hGBuY4pk0XD/0Ao/oTe/XGrfyM773aB7iUhgkpy+dwAMalxMP0DrBcsVw/6p25+/hobP9
GBknrWExDhLJ1bwt1NcCNblaFbMKCyvmX0PeRaQ=
""")

##file distutils.cfg
DISTUTILS_CFG = convert("""
eJxNj00KwkAMhfc9xYNuxe4Ft57AjYiUtDO1wXSmNJnK3N5pdSEEAu8nH6lxHVlRhtDHMPATA4uH
xJ4EFmGbvfJiicSHFRzUSISMY6hq3GLCRLnIvSTnEefN0FIjw5tF0Hkk9Q5dRunBsVoyFi24aaLg
9FDOlL0FPGluf4QjcInLlxd6f6rqkgPu/5nHLg0cXCscXoozRrP51DRT3j9QNl99AP53T2Q=
""")

##file activate_this.py
ACTIVATE_THIS = convert("""
eJyNU01v2zAMvetXEB4K21jnDOstQA4dMGCHbeihlyEIDMWmE62yJEiKE//7kXKdpEWLzYBt8evx
kRSzLPs6wiEoswM8YdMpjUXcq1Dz6RZa1cSiTkJdr86GsoTRHuCotBayiWqQEYGtMCgfD1KjGYBe
5a3p0cRKiEe2NtLAFikftnDco0ko/SFEVgEZ8aRCZDIPY9xbA8pE9M4jfW/B2CjiHq9zbJVZuOQq
siwTIvpxKYCembPAU4Muwi/Z4zfvrZ/MXipKeB8C+qisSZYiWfjJfs+0/MFMdWn1hJcO5U7G/SLa
xVx8zU6VG/PXLXvfsyyzUqjeWR8hjGE+2iCE1W1tQ82hsCJN9dzKaoexyB/uH79TnjwvxcW0ntSb
yZ8jq1Z5Q1UXsyy3gf9nbjTEj7NzQMfCJa/YSmrQ+2D/BqfiOi6sclrGzvoeVivIj8rcfcmnIQRF
7XCyeZI7DFe5/lhlCs5PRf5QW66VXT/NrlQ46oD/D6InkOmi3IQcbhKxAX2g4a+Xd5s3UtCtG2py
m8eg6WYWqR6SL5OjKMGfSrYt/6kxxQtOpeAgj1LXBNmpE2ElmCSIy5H0zFd8gJ924HWijWhb2hRC
6wNEm1QdDZtuSZcEprIUBo/XRNcbQe1OUbQ/r3hPTaPJJDNtFLu8KHV5XoNr3Eo6h6YtOKw8e8yw
VF5PnJ+ts3a9/Mz38RpG/AUSzYUW
""")

MH_MAGIC = 0xfeedface
MH_CIGAM = 0xcefaedfe
MH_MAGIC_64 = 0xfeedfacf
MH_CIGAM_64 = 0xcffaedfe
FAT_MAGIC = 0xcafebabe
BIG_ENDIAN = '>'
LITTLE_ENDIAN = '<'
LC_LOAD_DYLIB = 0xc
maxint = majver == 3 and getattr(sys, 'maxsize') or getattr(sys, 'maxint')


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
        return '<fileview [%d, %d] %r>' % (
            self._start, self._end, self._fileobj)

    def tell(self):
        return self._pos

    def _checkwindow(self, seekto, op):
        if not (self._start <= seekto <= self._end):
            raise IOError("%s to offset %d is outside window [%d, %d]" % (
                op, seekto, self._start, self._end))

    def seek(self, offset, whence=0):
        seekto = offset
        if whence == os.SEEK_SET:
            seekto += self._start
        elif whence == os.SEEK_CUR:
            seekto += self._start + self._pos
        elif whence == os.SEEK_END:
            seekto += self._end
        else:
            raise IOError("Invalid whence argument to seek: %r" % (whence,))
        self._checkwindow(seekto, 'seek')
        self._fileobj.seek(seekto)
        self._pos = seekto - self._start

    def write(self, bytes):
        here = self._start + self._pos
        self._checkwindow(here, 'write')
        self._checkwindow(here + len(bytes), 'write')
        self._fileobj.seek(here, os.SEEK_SET)
        self._fileobj.write(bytes)
        self._pos += len(bytes)

    def read(self, size=maxint):
        assert size >= 0
        here = self._start + self._pos
        self._checkwindow(here, 'read')
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
    res = struct.unpack(endian + 'L' * num, file.read(num * 4))
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
        for n in range(ncmds):
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
                load = load[:load.index('\0')]
                # If the string is what is being replaced, overwrite it.
                if load == what:
                    file.seek(where + name_offset, os.SEEK_SET)
                    file.write(value.encode() + '\0'.encode())
            # Seek to the next command
            file.seek(where + cmdsize, os.SEEK_SET)

    def do_file(file, offset=0, size=maxint):
        file = fileview(file, offset, size)
        # Read magic number
        magic = read_data(file, BIG_ENDIAN)
        if magic == FAT_MAGIC:
            # Fat binaries contain nfat_arch Mach-O binaries
            nfat_arch = read_data(file, BIG_ENDIAN)
            for n in range(nfat_arch):
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

    assert(len(what) >= len(value))
    do_file(open(path, 'r+b'))


if __name__ == '__main__':
    main()

## TODO:
## Copy python.exe.manifest
## Monkeypatch distutils.sysconfig
