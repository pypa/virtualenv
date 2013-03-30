#!/usr/bin/env python
"""Create a "virtual" Python installation
"""

# If you change the version here, change it in setup.py
# and docs/conf.py as well.
__version__ = "1.10.dev1"  # following best practices
virtualenv_version = __version__  # legacy, again

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

if sys.version_info < (2, 5):
    print('ERROR: %s' % sys.exc_info()[1])
    print('ERROR: this script requires Python 2.5 or greater.')
    sys.exit(101)

try:
    set
except NameError:
    from sets import Set as set
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
    if minver <= 3:
        REQUIRED_MODULES.extend(['sets', '__future__'])
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
    if minver == 3:
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
        logger.info('Creating parent directories for %s' % os.path.dirname(dest))
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

def _install_req(py_executable, unzip=False, distribute=False,
                 search_dirs=None, never_download=False):

    if search_dirs is None:
        search_dirs = file_search_dirs()

    if not distribute:
        egg_path = 'setuptools-*-py%s.egg' % sys.version[:3]
        found, egg_path = _find_file(egg_path, search_dirs)
        project_name = 'setuptools'
        bootstrap_script = EZ_SETUP_PY
        tgz_path = None
    else:
        # Look for a distribute egg (these are not distributed by default,
        # but can be made available by the user)
        egg_path = 'distribute-*-py%s.egg' % sys.version[:3]
        found, egg_path = _find_file(egg_path, search_dirs)
        project_name = 'distribute'
        if found:
            tgz_path = None
            bootstrap_script = DISTRIBUTE_FROM_EGG_PY
        else:
            # Fall back to sdist
            # NB: egg_path is not None iff tgz_path is None
            # iff bootstrap_script is a generic setup script accepting
            # the standard arguments.
            egg_path = None
            tgz_path = 'distribute-*.tar.gz'
            found, tgz_path = _find_file(tgz_path, search_dirs)
            bootstrap_script = DISTRIBUTE_SETUP_PY

    if is_jython and os._name == 'nt':
        # Jython's .bat sys.executable can't handle a command line
        # argument with newlines
        fd, ez_setup = tempfile.mkstemp('.py')
        os.write(fd, bootstrap_script)
        os.close(fd)
        cmd = [py_executable, ez_setup]
    else:
        cmd = [py_executable, '-c', bootstrap_script]
    if unzip and egg_path:
        cmd.append('--always-unzip')
    env = {}
    remove_from_env = ['__PYVENV_LAUNCHER__']
    if logger.stdout_level_matches(logger.DEBUG) and egg_path:
        cmd.append('-v')

    old_chdir = os.getcwd()
    if egg_path is not None and os.path.exists(egg_path):
        logger.info('Using existing %s egg: %s' % (project_name, egg_path))
        cmd.append(egg_path)
        if os.environ.get('PYTHONPATH'):
            env['PYTHONPATH'] = egg_path + os.path.pathsep + os.environ['PYTHONPATH']
        else:
            env['PYTHONPATH'] = egg_path
    elif tgz_path is not None and os.path.exists(tgz_path):
        # Found a tgz source dist, let's chdir
        logger.info('Using existing %s egg: %s' % (project_name, tgz_path))
        os.chdir(os.path.dirname(tgz_path))
        # in this case, we want to be sure that PYTHONPATH is unset (not
        # just empty, really unset), else CPython tries to import the
        # site.py that it's in virtualenv_support
        remove_from_env.append('PYTHONPATH')
    elif never_download:
        logger.fatal("Can't find any local distributions of %s to install "
                     "Please place a %s distribution (%s) in one of these "
                     "locations: %r" % (project_name, project_name,
                                        egg_path or tgz_path,
                                        search_dirs))
        sys.exit(1)
    elif egg_path:
        logger.info('No %s egg found; downloading' % project_name)
        cmd.extend(['--always-copy', '-U', project_name])
    else:
        logger.info('No %s tgz found; downloading' % project_name)
    logger.start_progress('Installing %s...' % project_name)
    logger.indent += 2
    cwd = None
    if project_name == 'distribute':
        env['DONT_PATCH_SETUPTOOLS'] = 'true'

    def _filter_ez_setup(line):
        return filter_ez_setup(line, project_name)

    if not os.access(os.getcwd(), os.W_OK):
        cwd = tempfile.mkdtemp()
        if tgz_path is not None and os.path.exists(tgz_path):
            # the current working dir is hostile, let's copy the
            # tarball to a temp dir
            target = os.path.join(cwd, os.path.split(tgz_path)[-1])
            shutil.copy(tgz_path, target)
    try:
        call_subprocess(cmd, show_stdout=False,
                        filter_stdout=_filter_ez_setup,
                        extra_env=env,
                        remove_from_env=remove_from_env,
                        cwd=cwd)
    finally:
        logger.indent -= 2
        logger.end_progress()
        if cwd is not None:
            shutil.rmtree(cwd)
        if os.getcwd() != old_chdir:
            os.chdir(old_chdir)
        if is_jython and os._name == 'nt':
            os.remove(ez_setup)

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

def install_setuptools(py_executable, unzip=False,
                       search_dirs=None, never_download=False):
    _install_req(py_executable, unzip,
                 search_dirs=search_dirs, never_download=never_download)

def install_distribute(py_executable, unzip=False,
                       search_dirs=None, never_download=False):
    _install_req(py_executable, unzip, distribute=True,
                 search_dirs=search_dirs, never_download=never_download)

_pip_re = re.compile(r'^pip-.*(zip|tar.gz|tar.bz2|tgz|tbz)$', re.I)
def install_pip(py_executable, search_dirs=None, never_download=False):
    if search_dirs is None:
        search_dirs = file_search_dirs()

    filenames = []
    for dir in search_dirs:
        filenames.extend([join(dir, fn) for fn in os.listdir(dir)
                          if _pip_re.search(fn)])
    filenames = [(os.path.basename(filename).lower(), i, filename) for i, filename in enumerate(filenames)]
    filenames.sort()
    filenames = [filename for basename, i, filename in filenames]
    if not filenames:
        filename = 'pip'
    else:
        filename = filenames[-1]
    easy_install_script = 'easy_install'
    if is_win:
        easy_install_script = 'easy_install-script.py'
    # There's two subtle issues here when invoking easy_install.
    # 1. On unix-like systems the easy_install script can *only* be executed
    #    directly if its full filesystem path is no longer than 78 characters.
    # 2. A work around to [1] is to use the `python path/to/easy_install foo`
    #    pattern, but that breaks if the path contains non-ASCII characters, as
    #    you can't put the file encoding declaration before the shebang line.
    # The solution is to use Python's -x flag to skip the first line of the
    # script (and any ASCII decoding errors that may have occurred in that line)
    cmd = [py_executable, '-x', join(os.path.dirname(py_executable), easy_install_script), filename]
    # jython and pypy don't yet support -x
    if is_jython or is_pypy:
        cmd.remove('-x')
    if filename == 'pip':
        if never_download:
            logger.fatal("Can't find any local distributions of pip to "
                         "install. Please place a pip source distribution "
                         "(zip/tar.gz/tar.bz2) in one of these "
                         "locations: %r" % search_dirs)
            sys.exit(1)
        logger.info('Installing pip from network...')
    else:
        logger.info('Installing existing %s distribution: %s' % (
                os.path.basename(filename), filename))
    logger.start_progress('Installing pip...')
    logger.indent += 2
    def _filter_setup(line):
        return filter_ez_setup(line, 'pip')
    try:
        call_subprocess(cmd, show_stdout=False,
                        filter_stdout=_filter_setup)
    finally:
        logger.indent -= 2
        logger.end_progress()

def filter_ez_setup(line, project_name='setuptools'):
    if not line.strip():
        return Logger.DEBUG
    if project_name == 'distribute':
        for prefix in ('Extracting', 'Now working', 'Installing', 'Before',
                       'Scanning', 'Setuptools', 'Egg', 'Already',
                       'running', 'writing', 'reading', 'installing',
                       'creating', 'copying', 'byte-compiling', 'removing',
                       'Processing'):
            if line.startswith(prefix):
                return Logger.DEBUG
        return Logger.DEBUG
    for prefix in ['Reading ', 'Best match', 'Processing setuptools',
                   'Copying setuptools', 'Adding setuptools',
                   'Installing ', 'Installed ']:
        if line.startswith(prefix):
            return Logger.DEBUG
    return Logger.INFO


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
    Custom option parser which updates its defaults by by checking the
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
        help="Increase verbosity")

    parser.add_option(
        '-q', '--quiet',
        action='count',
        dest='quiet',
        default=0,
        help='Decrease verbosity')

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
        help="Clear out the non-root install and start from scratch")

    parser.set_defaults(system_site_packages=False)
    parser.add_option(
        '--no-site-packages',
        dest='system_site_packages',
        action='store_false',
        help="Don't give access to the global site-packages dir to the "
             "virtual environment (default)")

    parser.add_option(
        '--system-site-packages',
        dest='system_site_packages',
        action='store_true',
        help="Give access to the global site-packages dir to the "
             "virtual environment")

    parser.add_option(
        '--always-copy',
        dest='symlink',
        action='store_false',
        default=True,
        help="Always copy files rather than symlinking")

    parser.add_option(
        '--unzip-setuptools',
        dest='unzip_setuptools',
        action='store_true',
        help="Unzip Setuptools or Distribute when installing it")

    parser.add_option(
        '--relocatable',
        dest='relocatable',
        action='store_true',
        help='Make an EXISTING virtualenv environment relocatable.  '
        'This fixes up scripts and makes all .pth files relative')

    parser.add_option(
        '--distribute', '--use-distribute',  # the second option is for legacy reasons here. Hi Kenneth!
        dest='use_distribute',
        action='store_true',
        help='Use Distribute instead of Setuptools. Set environ variable '
        'VIRTUALENV_DISTRIBUTE to make it the default ')

    parser.add_option(
        '--no-setuptools',
        dest='no_setuptools',
        action='store_true',
        help='Do not install distribute/setuptools (or pip) '
        'in the new virtualenv.')

    parser.add_option(
        '--no-pip',
        dest='no_pip',
        action='store_true',
        help='Do not install pip in the new virtualenv.')

    parser.add_option(
        '--setuptools',
        dest='use_distribute',
        action='store_false',
        help='Use Setuptools instead of Distribute.  Set environ variable '
        'VIRTUALENV_SETUPTOOLS to make it the default ')

    # Set this to True to use distribute by default, even in Python 2.
    parser.set_defaults(use_distribute=False)

    default_search_dirs = file_search_dirs()
    parser.add_option(
        '--extra-search-dir',
        dest="search_dirs",
        action="append",
        default=default_search_dirs,
        help="Directory to look for setuptools/distribute/pip distributions in. "
        "You can add any number of additional --extra-search-dir paths.")

    parser.add_option(
        '--never-download',
        dest="never_download",
        action="store_true",
        default=True,
        help="Never download anything from the network. This is now always "
        "the case. The option is only retained for backward compatibility, "
        "and does nothing. Virtualenv will fail if local distributions "
        "of setuptools/distribute/pip are not present.")

    parser.add_option(
        '--prompt',
        dest='prompt',
        help='Provides an alternative prompt prefix for this environment')

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

    # Force --distribute on Python 3, since setuptools is not available.
    if majver > 2:
        options.use_distribute = True

    if os.environ.get('PYTHONDONTWRITEBYTECODE') and not options.use_distribute:
        print(
            "The PYTHONDONTWRITEBYTECODE environment variable is "
            "not compatible with setuptools. Either use --distribute "
            "or unset PYTHONDONTWRITEBYTECODE.")
        sys.exit(2)
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
                       use_distribute=options.use_distribute,
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


def create_environment(home_dir, site_packages=False, clear=False,
                       unzip_setuptools=False, use_distribute=False,
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
        if use_distribute:
            install_distribute(py_executable, unzip=unzip_setuptools,
                               search_dirs=search_dirs, never_download=never_download)
        else:
            install_setuptools(py_executable, unzip=unzip_setuptools,
                               search_dirs=search_dirs, never_download=never_download)

        if not no_pip:
            install_pip(py_executable, search_dirs=search_dirs, never_download=never_download)

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
          os.unsetenv('__PYVENV_LAUNCHER__')
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
                shutil.copyfile(py_executable_base, full_pth)

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
                    cp_or_ln = (os.symlink if symlink else copyfile)
                    cp_or_ln(os.path.abspath(os.path.join(home_dir, subdir_name)), \
                                                            os.path.join(local_path, subdir_name))

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
                  'activate', 'activate.bat', 'activate_this.py']

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
/B+mKuo5
""")

##file ez_setup.py
EZ_SETUP_PY = convert("""
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
qL7+C1AkCcw=
""")

##file distribute_from_egg.py
DISTRIBUTE_FROM_EGG_PY = convert("""
eJw9j8tqAzEMRfcG/4MgmxQyptkGusonZBmGoGTUGYFfWPKE6dfXTkM3gqt7rh47OKP3NMF3SQFW
LlrRU1zhybpAxoKBlIqcrNnBdRjQP3GTocYfzmNrrCPQPN9iwzpxSQfQhWBi0cL3qtRtYIG/4Mv0
KApY5hooqrOGQ05FQTaxptF9Fnx16Rq0XofjaE1XGXVxHIWK7j8P8EY/rHndLqQ1a0pe3COFgHFy
hLLdWkDbi/DeEpCjNb3u/zccT2Ob8gtnwVyI
""")

##file distribute_setup.py
DISTRIBUTE_SETUP_PY = convert("""
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
eJyVVWFv2jAQ/c6vuBoqQVWC9nVSNVGVCaS2VC2rNLWVZZILWAs2s52wVvvxsyEJDrjbmgpK7PP5
3bt3d22YLbmGlGcIq1wbmCPkGhPYcLMEEsGciwGLDS+YwSjlekngLFVyBe73GXSXxqw/DwbuTS8x
yyKpFr1WG15lDjETQhpQuQBuIOEKY5O9tlppLqxHKSDByjVAPwEy+mXtCq5MzjIUBTCRgEKTKwFG
gpBqxTLYXgN2myspVigMaYF92tZSowGZJf4mFExxNs9Qb614CgZtmH0BpEOn11f0cXI/+za8pnfD
2ZjA1sg9zlV/8QvcMhxbNu0QwgYokn/d+n02nt6Opzcjcnx1vXcIoN74O4ymWQXmHURfJw9jenc/
vbmb0enj6P5+cuVhqlKm3S0u2XRtRbA2QQAhV7VhBF0rsgUX9Ur1rBUXJgVSy8O751k8mzY5OrKH
RW3eaQhYGTr8hrXO59ALhxQ83mCsDLAid3T72CCSdJhaFE+fXgicXAARUiR2WeVO37gH3oYHzFKo
9k7CaPZ1UeNwH1tWuXA4uFKYYcEa8vaKqXl7q1UpygMPhFLvlVKyNzsSM3S2km7UBOl4xweUXk5u
6e3wZmQ9leY1XE/Ili670tr9g/5POBBpGIJXCCF79L1siarl/dbESa8mD8PL61GpzqpzuMS7tqeB
1YkALrRBloBMbR9yLcVx7frQAgUqR7NZIuzkEu110gbNit1enNs82Rx5utq7Z3prU78HFRgulqNC
OTwbqJa9vkJFclQgZSjbKeBgSsUtCtt9D8OwAbIVJuewQdfvQRaoFE9wd1TmCuRG7OgJ1bVXGHc7
z5WDL/WW36v2oi37CyVBak61+yPBA9C1qqGxzKQqZ0oPuocU9hpud0PIp8sDHkXR1HKkNlzjuUWA
a0enFUyzOWZA4yXGP+ZMI3Tdt2OuqU/SO4q64526cPE0A7ZyW2PMbWZiZ5HamIZ2RcCKLXhcDl2b
vXL+eccQoRzem80mekPDEiyiWK4GWqZmwxQOmPM0eIfgp1P9cqrBsewR2p/DPMtt+pfcYM+Ls2uh
hALufTAdmGl8B1H3VPd2af8fQAc4PgqjlIBL9cGQqNpXaAwe3LrtVn8AkZTUxg==
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
