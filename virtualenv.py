#!/usr/bin/env python
"""Create a "virtual" Python installation
"""

__version__ = "1.12.dev1"
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
import sysconfig

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
                    'sysconfig', 'zlib']

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
                    print("An error occured during configuration: %s" % e)
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
    paths = sysconfig.get_paths(vars={'base':home_dir, 'platbase':home_dir})
    lib_dir = paths['stdlib']
    inc_dir = paths['include']
    bin_dir = paths['scripts']
    if not is_win:
        multiarch_exec = '/usr/bin/multiarch-platform'
        if is_executable_file(multiarch_exec):
            # In Mageia (2) and Mandriva distros the include dir must be like:
            # virtualenv/include/multiarch-x86_64-linux/python2.7
            # instead of being virtualenv/include/python2.7
            p = subprocess.Popen(multiarch_exec, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            stdout, stderr = p.communicate()
            # stdout.strip is needed to remove newline character
            inc_dir = join(home_dir, 'include', stdout.strip(), py_version + abiflags)
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

    stdinc_dir = sysconfig.get_path('include')
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
        exec_dir = sysconfig.get_path('stdlib')
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
                for name in 'libexpat.dll', 'libpypy.dll', 'libpypy-c.dll', 'libeay32.dll', 'ssleay32.dll', 'sqlite.dll':
                    src = join(prefix, name)
                    if os.path.exists(src):
                        copyfile(src, join(bin_dir, name), symlink)

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
            # Make sure we use the the embedded interpreter inside
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
        cp_or_ln = (os.symlink if symlink else copyfile)
        cp_or_ln('lib', lib64_link)

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
O9EegDUKwf8CoRMeiQ==
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
eJylWdmS40Z2fVeE/oHT6rCloNUEAXDThB6wAyQAEjsB29GBjdgXYiWgmC/zgz/Jv+AEWNVd3S2N
xuOKYEUxM+/Jmzfvcm7W//zXf/+wUMOoXtyi1F9kbd0sHH/hFc2iLtrK9b3FrSqyxaVQwr8uhqJd
uHaeg9mqzRdR8/13Pyy8qPLdJh0+LMhi0QCoXxYfFh9WtttEnd34H8p6/f1300KauwrULws39e18
0ZaLNm9rgN/ZVf3h++/e124Vlc0vKsspHy+Yyi5+XbzPhijvCtduoiL/kA1ukWV27n0o7Sb8LIFj
CvWR5GQgUJdp1Pw8TS9+rPy6SDv/+e3d+0+4qw8f3v20+PliV37efEYBAB9FTKC+RHn/Cfxn3rdv
00Fube5O+iyCtHDs9BfPfz3q4sfFv9d91Ljhfy7ei0VO+nVTtdOkv/jpt0l2AX6iG1jXgKnnDuD4
ke2k/i8fzzz5UedkVcP4pwF+Wvz2FJl+3vt598urXf5Y6LNA5WcFOP7r0sW7b9a+W/xcu0Xpv5zk
Kfq3P9Dz9di/fCxS72MXVU1rpx9L4Bxl85Wmn5a+zP76Zuh3pL9ROWr87PN+//GHIl+oOtvn9XSU
qH+p0gQBFnx1uV+JLH5O5zv+PXW+WepXVVHZT0+oQezkIATcIm+ivPV/z5J/+cYj3ir4w0Lx09vC
e5n/y5/Y5LPPfdrqb88ga/PabxZRVfmp39l588m/6u+/e+OpP+dF7n1WZpJ9//Z4v372fDDz9eHB
7Juvs/BLMHzrxL9+9twXpJfhd1/DrpQ5Euu/vlss3wp9HXC/54C/Ld69m6zwdx3tC0d8daSv0V8B
n4b9YYF53sJelJV/ix6LZspw/sJtqyl5LJ5r/23htA1Imfm/gt9R7dqVB1LjhydAX4Gb+zksQF59
9+P7H//U+376afFuvh2/T6P85Xr/5c8C6OXyFY4BGuN+EE0+GeR201b+wkkLN5mmBY5TfMw8ngqL
CztXxCSXKMCYrRIElWkEJlEPYsSOeKBVZCAQTKBhApMwRFQzmCThE0YQu2CdEhgjbgmk9GluHpfR
/hhwJCZhGI5jt5FsAkOrObVyE6g2y1snyhMGFlDY1x+BoHpCMulTj5JYWNAYJmnKpvLxXgmQ8az1
4fUGxxcitMbbhDFcsiAItg04E+OSBIHTUYD1HI4FHH4kMREPknuYRMyhh3AARWMkfhCketqD1CWJ
mTCo/nhUScoQcInB1hpFhIKoIXLo5jLpwFCgsnLCx1QlEMlz/iFEGqzH3vWYcpRcThgWnEKm0QcS
rA8ek2a2IYYeowUanOZOlrbWSJUC4c7y2EMI3uJPMnMF/SSXdk6E495VLhzkWHps0rOhKwqk+xBI
DhJirhdUCTamMfXz2Hy303hM4DFJ8QL21BcPBULR+gcdYxoeiDqOFSqpi5B5PUISfGg46gFZBPo4
jdh8lueaWuVSMTURfbAUnLINr/QYuuYoMQV6l1aWxuZVTjlaLC14UzqZ+ziTGDzJzhiYoPLrt3uI
tXkVR47kAo09lo5BD76CH51cTt1snVpMOttLhY93yxChCQPI4OBecS7++h4p4Bdn4H97bJongtPk
s9gQnXku1vzsjjmX4/o4YUDkXkjHwDg5FXozU0fW4y5kyeYW0uJWlh536BKr0kMGjtzTkng6Ep62
uTWnQtiIqKnEsx7e1hLtzlXs7Upw9TwEnp0t9yzCGgUJIZConx9OHJArLkRYW0dW42G9OeR5Nzwk
yk1mX7du5RGHT7dka7N3AznmSif7y6tuKe2N1Al/1TUPRqH6E2GLVc27h9IptMLkCKQYRqPQJgzV
2m6WLsSipS3v3b1/WmXEYY1meLEVIU/arOGVkyie7ZsH05ZKpjFW4cpY0YkjySpSExNG2TS8nnJx
nrQmWh2WY3cP1eISP9wbaVK35ZXc60yC3VN/j9n7UFoK6zvjSTE2+Pvz6Mx322rnftfP8Y0XKIdv
Qd7AfK0nexBTMqRiErvCMa3Hegpfjdh58glW2oNMsKeAX8x6YJLZs9K8/ozjJkWL+JmECMvhQ54x
9rsTHwcoGrDi6Y4I+H7yY4/rJVPAbYymUH7C2D3uiUS3KQ1nrCAUkE1dJMneDQIJMQQx5SONxoEO
OEn1/Ig1eBBUeEDRuOT2WGGGE4bNypBLFh2PeIg3bEbg44PHiqNDbGIQm50LW6MJU62JHCGBrmc9
2F7WBJrrj1ssnTAK4sxwRgh5LLblhwNAclv3Gd+jC/etCfyfR8TMhcWQz8TBIbG8IIyAQ81w2n/C
mHWAwRzxd3WoBY7BZnsqGOWrOCKwGkMMNfO0Kci/joZgEocLjNnzgcmdehPHJY0FudXgsr+v44TB
I3jnMGnsK5veAhgi9iXGifkHMOC09Rh9cAw9sQ0asl6wKMk8mpzFYaaDSgG4F0wisQDDBRpjCINg
FIxhlhQ31xdSkkk6odXZFpTYOQpOOgw9ugM2cDQ+2MYa7JsEirGBrOuxsQy5nPMRdYjsTJ/j1iNw
FeSt1jY2+dd5yx1/pzZMOQXUIDcXeAzR7QlDRM8AMkUldXOmGmvYXPABjxqkYKO7VAY6JRU7kpXr
+Epu2BU3qFFXClFi27784LrDZsJwbNlDw0JzhZ6M0SMXE4iBHehCpHVkrQhpTFn2dsvsZYkiPEEB
GSEAwdiur9LS1U6P2U9JhGp4hnFpJo4FfkdJHcwV6Q5dV1Q9uNeeu7rV8PAjwdFg9RLtroifOr0k
uOiRTo/obNPhQIf42Fr4mtThWoSjitEdAmFW66UCe8WFjPk1YVNpL9srFbond7jrLg8tqAasIMpy
zkH0SY/6zVAwJrEc14zt14YRXdY+fcJ4qOd2XKB0/Kghw1ovd11t2o+zjt+txndo1ZDZ2T+uMVHT
VSXhedBAHoJIID9xm6wPQI3cXY+HR7vxtrJuCKh6kbXaW5KkVeJsdsjqsYsOwYSh0w5sMbu7LF8J
5T7U6LJdiTx+ca7RKlulGgS5Z1JSU2Llt32cHFipkaurtBrvNX5UtvNZjkufZ/r1/XyLl6yOpytL
Km8Fn+y4wkhlqZP5db0rooqy7xdL4wxzFVTX+6HaxuQJK5E5B1neSSovZ9ALB8091dDbbjVxhWNY
Ve5hn1VnI9OF0wpvaRm7SZuC1IRczwC7GnkhPt3muHV1YxUJfo+uh1sYnJy+vI0ZwuPV2uqWJYUH
bmBsi1zmFSxHrqwA+WIzLrHkwW4r+bad7xbOzJCnKIa3S3YvrzEBK1Dc0emzJW+SqysQfdEDorQG
9ZJlbQzEHQV8naPaF440YXzJk/7vHGK2xwuP+Gc5xITxyiP+WQ4x18oXHjFzCBy9kir1EFTAm0Zq
LYwS8MpiGhtfxiBRDXpxDWxk9g9Q2fzPPAhS6VFDAc/aiNGatUkPtZIStZFQ1qD0IlJa/5ZPAi5J
ySp1ETDomZMnvgiysZSBfMikrSDte/K5lqV6iwC5q7YN9I1dBZXUytDJNqU74MJsUyNNLAPopWK3
tzmLkCiDyl7WQnj9sm7Kd5kzgpoccdNeMw/6zPVB3pUwMgi4C7hj4AMFAf4G27oXH8NNT9zll/sK
S6wVlQwazjxWKWy20ZzXb9ne8ngGalPBWSUSj9xkc1drsXkZ8oOyvYT3e0rnYsGwx85xZB9wKeKg
cJKZnamYwiaMymZvzk6wtDUkxmdUg0mPad0YHtvzpjEfp2iMxvORhnx0kCVLf5Qa43WJsVoyfEyI
pzmf8ruM6xBr7dnBgzyxpqXuUPYaKahOaz1LrxNkS/Q3Ae5AC+xl6NbxAqXXlzghZBZHmOrM6Y6Y
ctAkltwlF7SKEsShjVh7QHuxMU0a08/eiu3x3M+07OijMcKFFltByXrpk8w+JNnZpnp3CfgjV1Ax
gUYCnWwYow42I5wHCcTzLXK0hMZN2DrPM/zCSqe9jRSlJnr70BPE4+zrwbk/xVIDHy2FAQyHoomT
Tt5jiM68nBQut35Y0qLclLiQrutxt/c0OlSqXAC8VrxW97lGoRWzhOnifE2zbF05W4xuyhg7JTUL
aqJ7SWDywhjlal0b+NLTpERBgnPW0+Nw99X2Ws72gOL27iER9jgzj7Uu09JaZ3n+hmCjjvZpjNst
vOWWTbuLrg+/1ltX8WpPauEDEvcunIgTxuMEHweWKCx2KQ9DU/UKdO/3za4Szm2iHYL+ss9AAttm
gZHq2pkUXFbV+FiJCKrpBms18zH75vax5jSo7FNunrVWY3Chvd8KKnHdaTt/6ealwaA1x17yTlft
8VBle3nAE+7R0MScC3MJofNCCkA9PGKBgGMYEwfB2QO5j8zUqa8F/EkWKCzGQJ5EZ05HTly1B01E
z813G5BY++RZ2sxbQS8ZveGPJNabp5kXAeoign6Tlt5+L8i5ZquY9+S+KEUHkmYMRFBxRrHnbl2X
rVemKnG+oB1yd9+zT+4c43jQ0wWmQRR6mTCkY1q3VG05Y120ZzKOMBe6Vy7I5Vz4ygPB3yY4G0FP
8RxiMx985YJPXsgRU58EuHj75gygTzejP+W/zKGe78UQN3yOJ1aMQV9hFH+GAfLRsza84WlPLAI/
9G/5JdcHftEfH+Y3/fHUG7/o8bv98dzzy3e8S+XCvgqB+VUf7sH0yDHpONdbRE8tAg9NWOzcTJ7q
TuAxe/AJ07c1Rs9okJvl1/0G60qvbdDzz5zO0FuPFQIHNp9y9Bd1CufYVx7dB26mAxwa8GMNrN/U
oGbNZ3EQ7inLzHy5tRg9AXJrN8cB59cCUBeCiVO7zKM0jU0MamhnRThkg/NMmBOGb6StNeD9tDfA
7czsAWopDdnGoXUHtA+s/k0vNPkBcxEI13jVd/axp85va3LpwGggXXWw12Gwr/JGAH0b8CPboiZd
QO1l0mk/UHukud4C+w5uRoNzpCmoW6GbgbMyaQNkga2pQINB18lOXOCJzSWPFOhZcwzdgrsQnne7
nvjBi+7cP2BbtBeDOW5uOLGf3z94FasKIguOqJl+8ss/6Kumns4cuWbqq5592TN/RNIbn5Qo6qbi
O4F0P9txxPAwagqPlftztO8cWBzdN/jz3b7GD6JHYP/Zp4ToAMaA74M+EGSft3hEGMuf8EwjnTk/
nz/P7SLipB/ogQ6xNX0fDqNncMCfHqGLCMM0ZzFa+6lPJYQ5p81vW4HkCvidYf6kb+P/oB965g8K
C6uR0rdjX1DNKc5pOSTquI8uQ6KXxYaKBn+30/09tK4kMpJPgUIQkbENEPbuezNPPje2Um83SgyX
GTCJb6MnGVIpgncdQg1qz2bvPfxYD9fewCXDomx9S+HQJuX6W3VAL+v5WZMudRQZk9ZdOk6GIUtC
PqEb/uwSIrtR7/edzqgEdtpEwq7p2J5OQV+RLrmtTvFwFpf03M/VrRyTZ73qVod7v7Jh2Dwe5J25
JqFOU2qEu1sP+CRotklediycKfLjeIZzjJQsvKmiGSNQhxuJpKa+hoWUizaE1PuIRGzJqropwgVB
oo1hr870MZLgnXF5ZIpr6mF0L8aSy2gVnTAuoB4WEd4d5NPVC9TMotYXERKlTcwQ2KiB/C48AEfH
Qbyq4CN8xTFnTvf/ebOc3isnjD95s0QF0nx9s+y+zMmz782xL0SgEmRpA3x1w1Ff9/74xcxKEPdS
IEFTz6GgU0+BK/UZ5Gwbl4gZwycxEw+Kqa5QmMkh4OzgzEVPnDAiAOGBFaBW4wkDmj1G4RyElKgj
NlLCq8zsp085MNh/+R4t1Q8yxoSv8PUpTt7izZwf2BTHZZ3pIZpUIpuLkL1nNL6sYcHqcKm237wp
T2+RCjgXweXd2Zp7ZM8W6dG5bZsqo0nrJBTx8EC0+CQQdzEGnabTnkzofu1pYkWl4E7XSniECdxy
vLYavPMcL9LW5SToJFNnos+uqweOHriUZ1ntIYZUonc7ltEQ6oTRtwOHNwez2sVREskHN+bqG3ua
eaEbJ8XpyO8CeD9QJc8nbLP2C2R3A437ISUNyt5Yd0TbDNcl11/DSsOzdbi/VhCC0KE6v1vqVNkq
45ZnG6fiV2NwzInxCNth3BwL0+8814jE6+1W1EeWtpWbSZJOJNYXmWRXa7vLnAljE692eHjZ4y5u
y1u63De0IzKca7As48Z3XshVF+3XiLNz0JIMh/JOpbiNLlMi672uO0wYzOCZjRxcxj3D+gVenGIE
MvFUGGXuRps2RzMcgWIRolHXpGUP6sMsQt1hspUBnVKUn/WQj2u6j3SXd9Xz0QtEzoM7qTu5y7gR
q9gNNsrlEMLdikBt9bFvBnfbUIh6voTw7eDsyTmPKUvF0bHqWLbHe3VRHyRZnNeSGKsB73q66Vsk
taxWYmwz1tYVFG/vOQhlM0gUkyvIab3nv2caJ1udU1F3pDMty7stubTE4OJqm0i0ECfrJIkLtraC
HwRWKzlqpfhEIqYH09eT9WrOhQyt8YEoyBlnXtAT37WHIQ03TIuEHbnRxZDdLun0iok9PUC79prU
m5beZzfQUelEXnhzb/pIROKx3F7qCttYIFGh5dXNzFzID7u8vKykA8Uejf7XXz//S4nKvW//ofS/
QastYw==
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
eJyNU01v2zAMvetXEB4K21jmDOstQA4dMGCHbeihlyEIDMWmG62yJEiKE//7kXKdpN2KzYBt8euR
fKSyLPs8wiEo8wh4wqZTGou4V6Hm0wJa1cSiTkJdr8+GsoTRHuCotBayiWqQEYGtMCgfD1KjGYBe
5a3p0cRKiAe2NtLADikftnDco0ko/SFEVgEZ8aRC5GLux7i3BpSJ6J1H+i7A2CjiHq9z7JRZuuQq
siwTIvpxJYCeuWaBpwZdhB+yxy/eWz+ZvVSU8C4E9FFZkyxFsvCT/ZzL8gcz9aXVE14Yyp2M+2W0
y7n5mp0qN+avKXvbsyyzUqjeWR8hjGE+2iCE1W1tQ82hsCZN9UzlJr+/e/iab8WfqsmPI6pWeUPd
FrMsd4H/55poeO9n54COhUs+sZNEzNtg/wanpjpuqHJaxs76HtZryI/K3H7KJ/KDIhqcbJ7kI4ar
XL+sMgXnX0D+Te2Iy5xdP8yueSlQB/x/ED2BTAtyE3K4SYUN6AMNfbO63f4lBW3bUJPbTL+mjSxS
PyRfJkZRgj+VbFv+EzHFi5pKwUEepa4JslMnwkowSRCXI+m5XvEOvtuBrxHdhLalG0JofYBok6qj
YdN2dEngUlbC4PG60M1WEN0piu7Nq7on0mgyyUw3iV1etLo6r/81biWdQ9MWHFaePWZYaq+nmp+t
s3az+sj7eA0jfgPfeoN1
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
