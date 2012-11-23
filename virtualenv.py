#!/usr/bin/env python
"""Create a "virtual" Python installation
"""

# If you change the version here, change it in setup.py
# and docs/conf.py as well.
__version__ = "1.8.3"  # following best practices
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

def copyfileordir(src, dest):
    if os.path.isdir(src):
        shutil.copytree(src, dest, True)
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
            copyfileordir(src, dest)
    else:
        logger.info('Copying to %s', dest)
        copyfileordir(src, dest)

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
        if files and os.path.exists(files[0]):
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
                     "and --never-download is set.  Either re-run virtualenv "
                     "without the --never-download option, or place a %s "
                     "distribution (%s) in one of these "
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
            logger.fatal("Can't find any local distributions of pip to install "
                         "and --never-download is set.  Either re-run virtualenv "
                         "without the --never-download option, or place a pip "
                         "source distribution (zip/tar.gz/tar.bz2) in one of these "
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
        help="Never download anything from the network.  Instead, virtualenv will fail "
        "if local distributions of setuptools/distribute/pip are not present.")

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

    create_environment(home_dir,
                       site_packages=options.system_site_packages,
                       clear=options.clear,
                       unzip_setuptools=options.unzip_setuptools,
                       use_distribute=options.use_distribute,
                       prompt=options.prompt,
                       search_dirs=options.search_dirs,
                       never_download=options.never_download)
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
                       prompt=None, search_dirs=None, never_download=False):
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
        site_packages=site_packages, clear=clear))

    install_distutils(home_dir)

    if use_distribute:
        install_distribute(py_executable, unzip=unzip_setuptools,
                           search_dirs=search_dirs, never_download=never_download)
    else:
        install_setuptools(py_executable, unzip=unzip_setuptools,
                           search_dirs=search_dirs, never_download=never_download)

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

def copy_required_modules(dst_prefix):
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
                # special-case custom readline.so on OS X:
                if modname == 'readline' and sys.platform == 'darwin' and not filename.endswith(join('lib-dynload', 'readline.so')):
                    dst_filename = join(dst_prefix, 'lib', 'python%s' % sys.version[:3], 'readline.so')
                else:
                    dst_filename = change_prefix(filename, dst_prefix)
                copyfile(filename, dst_filename)
                if filename.endswith('.pyc'):
                    pyfile = filename[:-1]
                    if os.path.exists(pyfile):
                        copyfile(pyfile, dst_filename[:-1])
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


def install_python(home_dir, lib_dir, inc_dir, bin_dir, site_packages, clear):
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
    fix_lib64(lib_dir)
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
                    copyfile(join(stdlib_dir, fn), join(lib_dir, fn))
        # ...and modules
        copy_required_modules(home_dir)
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
        copyfile(stdinc_dir, inc_dir)
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
            copyfile(platinc_dir, platinc_dest)

    # pypy never uses exec_prefix, just ignore it
    if sys.exec_prefix != prefix and not is_pypy:
        if is_win:
            exec_dir = join(sys.exec_prefix, 'lib')
        elif is_jython:
            exec_dir = join(sys.exec_prefix, 'Lib')
        else:
            exec_dir = join(sys.exec_prefix, 'lib', py_version)
        for fn in os.listdir(exec_dir):
            copyfile(join(exec_dir, fn), join(lib_dir, fn))

    if is_jython:
        # Jython has either jython-dev.jar and javalib/ dir, or just
        # jython.jar
        for name in 'jython-dev.jar', 'javalib', 'jython.jar':
            src = join(prefix, name)
            if os.path.exists(src):
                copyfile(src, join(home_dir, name))
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
        if is_cygwin and os.path.exists(executable + '.exe'):
            # Cygwin misreports sys.executable sometimes
            executable += '.exe'
            py_executable += '.exe'
            logger.info('Executable actually exists in %s' % executable)
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
            copyfile(py_executable, python_executable)

            if is_win:
                for name in 'libexpat.dll', 'libpypy.dll', 'libpypy-c.dll', 'libeay32.dll', 'ssleay32.dll', 'sqlite.dll':
                    src = join(prefix, name)
                    if os.path.exists(src):
                        copyfile(src, join(bin_dir, name))

    if os.path.splitext(os.path.basename(py_executable))[0] != expected_exe:
        secondary_exe = os.path.join(os.path.dirname(py_executable),
                                     expected_exe)
        py_executable_ext = os.path.splitext(py_executable)[1]
        if py_executable_ext == '.exe':
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
            virtual_lib)

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
            os.symlink(py_executable_base, full_pth)

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

    fix_local_scheme(home_dir)

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

def fix_local_scheme(home_dir):
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
                    os.symlink(os.path.abspath(os.path.join(home_dir, subdir_name)), \
                                                            os.path.join(local_path, subdir_name))

def fix_lib64(lib_dir):
    """
    Some platforms (particularly Gentoo on x64) put things in lib64/pythonX.Y
    instead of lib/pythonX.Y.  If this is such a platform we'll just create a
    symlink so lib64 points to lib
    """
    if [p for p in distutils.sysconfig.get_config_vars().values()
        if isinstance(p, basestring) and 'lib64' in p]:
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
        os.symlink('lib', lib64_link)

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
    fixup_scripts(home_dir)
    fixup_pth_and_egg_link(home_dir)
    ## FIXME: need to fix up distutils.cfg

OK_ABS_SCRIPTS = ['python', 'python%s' % sys.version[:3],
                  'activate', 'activate.bat', 'activate_this.py']

def fixup_scripts(home_dir):
    # This is what we expect at the top of scripts:
    shebang = '#!%s/bin/python' % os.path.normcase(os.path.abspath(home_dir))
    # This is what we'll put:
    new_shebang = '#!/usr/bin/env python%s' % sys.version[:3]
    if is_win:
        bin_suffix = 'Scripts'
    else:
        bin_suffix = 'bin'
    bin_dir = os.path.join(home_dir, bin_suffix)
    home_dir, lib_dir, inc_dir, bin_dir = path_locations(home_dir)
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
        if not lines[0].strip().startswith(shebang):
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
    activate = "import os; activate_this=os.path.join(os.path.dirname(os.path.realpath(__file__)), 'activate_this.py'); execfile(activate_this, dict(__file__=activate_this)); del os, activate_this"
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

    If you provide something like ``python_version='2.4'`` then the
    script will start with ``#!/usr/bin/env python2.4`` instead of
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
CP4PNIke9w==
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
eJxzSE3OyFfIT0vj4spMU0hJTcvMS01RiPf3cYkP8wwKCXX0iQ8I8vcNCFHQ4FIAguLUEgUliIit
KhZlqkpcnCA1WKRsuTTxWBIZ4uHv5+Hv64piEVwU3TK4BNBCmHIcKvDb6xjigWIjkI9uF1AIu7dA
akGGW7n6uXABALCXXUI=
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
