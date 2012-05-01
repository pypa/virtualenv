#!/usr/bin/env python
"""Create a "virtual" Python installation
"""

# If you change the version here, change it in setup.py
# and docs/conf.py as well.
virtualenv_version = "1.7.1.2.post1"

import base64
import sys
import os
import optparse
import re
import shutil
import logging
import tempfile
import zlib
import errno
import distutils.sysconfig
from distutils.util import strtobool

try:
    import subprocess
except ImportError:
    if sys.version_info <= (2, 3):
        print('ERROR: %s' % sys.exc_info()[1])
        print('ERROR: this script requires Python 2.4 or greater; or at least the subprocess module.')
        print('If you copy subprocess.py from a newer version of Python this script will probably work')
        sys.exit(101)
    else:
        raise
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
is_win  = (sys.platform == 'win32')
abiflags = getattr(sys, 'abiflags', '')

user_dir = os.path.expanduser('~')
if sys.platform == 'win32':
    user_dir = os.environ.get('APPDATA', user_dir)  # Use %APPDATA% for roaming
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
                             'shutil', 'struct', 'copy'])
    if minver >= 2:
        REQUIRED_FILES[-1] = 'config-%s' % majver
    if minver == 3:
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
            "bisect",
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
            "heapq",
            "hmac",
            #"html",
            #"http",
            #"idlelib",
            #"imaplib",
            #"imghdr",
            #"importlib",
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
            "reprlib",
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
            "weakref",
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
        self.log(self.WARN, msg, *args, **kw)
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
        if os.path.exists(join(dir, filename)):
            return join(dir, filename)
    return filename

def _install_req(py_executable, unzip=False, distribute=False,
                 search_dirs=None, never_download=False):

    if search_dirs is None:
        search_dirs = file_search_dirs()

    if not distribute:
        setup_fn = 'setuptools-0.6c11-py%s.egg' % sys.version[:3]
        project_name = 'setuptools'
        bootstrap_script = EZ_SETUP_PY
        source = None
    else:
        setup_fn = None
        source = 'distribute-0.6.24.tar.gz'
        project_name = 'distribute'
        bootstrap_script = DISTRIBUTE_SETUP_PY

    if setup_fn is not None:
        setup_fn = _find_file(setup_fn, search_dirs)

    if source is not None:
        source = _find_file(source, search_dirs)

    if is_jython and os._name == 'nt':
        # Jython's .bat sys.executable can't handle a command line
        # argument with newlines
        fd, ez_setup = tempfile.mkstemp('.py')
        os.write(fd, bootstrap_script)
        os.close(fd)
        cmd = [py_executable, ez_setup]
    else:
        cmd = [py_executable, '-c', bootstrap_script]
    if unzip:
        cmd.append('--always-unzip')
    env = {}
    remove_from_env = []
    if logger.stdout_level_matches(logger.DEBUG):
        cmd.append('-v')

    old_chdir = os.getcwd()
    if setup_fn is not None and os.path.exists(setup_fn):
        logger.info('Using existing %s egg: %s' % (project_name, setup_fn))
        cmd.append(setup_fn)
        if os.environ.get('PYTHONPATH'):
            env['PYTHONPATH'] = setup_fn + os.path.pathsep + os.environ['PYTHONPATH']
        else:
            env['PYTHONPATH'] = setup_fn
    else:
        # the source is found, let's chdir
        if source is not None and os.path.exists(source):
            logger.info('Using existing %s egg: %s' % (project_name, source))
            os.chdir(os.path.dirname(source))
            # in this case, we want to be sure that PYTHONPATH is unset (not
            # just empty, really unset), else CPython tries to import the
            # site.py that it's in virtualenv_support
            remove_from_env.append('PYTHONPATH')
        else:
            if never_download:
                logger.fatal("Can't find any local distributions of %s to install "
                             "and --never-download is set.  Either re-run virtualenv "
                             "without the --never-download option, or place a %s "
                             "distribution (%s) in one of these "
                             "locations: %r" % (project_name, project_name,
                                                setup_fn or source,
                                                search_dirs))
                sys.exit(1)

            logger.info('No %s egg found; downloading' % project_name)
        cmd.extend(['--always-copy', '-U', project_name])
    logger.start_progress('Installing %s...' % project_name)
    logger.indent += 2
    cwd = None
    if project_name == 'distribute':
        env['DONT_PATCH_SETUPTOOLS'] = 'true'

    def _filter_ez_setup(line):
        return filter_ez_setup(line, project_name)

    if not os.access(os.getcwd(), os.W_OK):
        cwd = tempfile.mkdtemp()
        if source is not None and os.path.exists(source):
            # the current working dir is hostile, let's copy the
            # tarball to a temp dir
            target = os.path.join(cwd, os.path.split(source)[-1])
            shutil.copy(source, target)
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
    if sys.platform == 'win32':
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
                if option.action in ('store_true', 'store_false', 'count'):
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

        defaults = self.update_defaults(self.defaults.copy()) # ours
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

    parser.add_option(
        '--no-site-packages',
        dest='no_site_packages',
        action='store_true',
        help="Don't give access to the global site-packages dir to the "
             "virtual environment (default; deprecated)")

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
        '--distribute',
        dest='use_distribute',
        action='store_true',
        help='Use Distribute instead of Setuptools. Set environ variable '
        'VIRTUALENV_DISTRIBUTE to make it the default ')

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
        '--prompt=',
        dest='prompt',
        help='Provides an alternative prompt prefix for this environment')

    if 'extend_parser' in globals():
        extend_parser(parser)

    options, args = parser.parse_args()

    global logger

    if 'adjust_options' in globals():
        adjust_options(options, args)

    verbosity = options.verbose - options.quiet
    logger = Logger([(Logger.level_for_integer(2-verbosity), sys.stdout)])

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

    if options.no_site_packages:
        logger.warn('The --no-site-packages flag is deprecated; it is now '
                    'the default behavior.')

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

    # use_distribute also is True if VIRTUALENV_DISTRIBUTE env var is set
    # we also check VIRTUALENV_USE_DISTRIBUTE for backwards compatibility
    if use_distribute or os.environ.get('VIRTUALENV_USE_DISTRIBUTE'):
        install_distribute(py_executable, unzip=unzip_setuptools,
                           search_dirs=search_dirs, never_download=never_download)
    else:
        install_setuptools(py_executable, unzip=unzip_setuptools,
                           search_dirs=search_dirs, never_download=never_download)

    install_pip(py_executable, search_dirs=search_dirs, never_download=never_download)

    install_activate(home_dir, bin_dir, prompt)

def path_locations(home_dir):
    """Return the path locations for the environment (where libraries are,
    where scripts go, etc)"""
    # XXX: We'd use distutils.sysconfig.get_python_inc/lib but its
    # prefix arg is broken: http://bugs.python.org/issue3386
    if sys.platform == 'win32':
        # Windows has lots of problems with executables with spaces in
        # the name; this function will remove them (using the ~1
        # format):
        mkdir(home_dir)
        if ' ' in home_dir:
            try:
                import win32api
            except ImportError:
                print('Error: the path "%s" has a space in it' % home_dir)
                print('To handle these kinds of paths, the win32api module must be installed:')
                print('  http://sourceforge.net/projects/pywin32/')
                sys.exit(3)
            home_dir = win32api.GetShortPathName(home_dir)
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
    elif sys.platform != 'win32':
        lib_dir = join(home_dir, 'lib', py_version)
        inc_dir = join(home_dir, 'include', py_version + abiflags)
        bin_dir = join(home_dir, 'bin')
    return home_dir, lib_dir, inc_dir, bin_dir


def change_prefix(filename, dst_prefix):
    prefixes = [sys.prefix]

    if sys.platform == "darwin":
        prefixes.extend((
            os.path.join("/Library/Python", sys.version[:3], "site-packages"),
            os.path.join(sys.prefix, "Extras", "lib", "python"),
            os.path.join("~", "Library", "Python", sys.version[:3], "site-packages")))

    if hasattr(sys, 'real_prefix'):
        prefixes.append(sys.real_prefix)
    prefixes = list(map(os.path.abspath, prefixes))
    filename = os.path.abspath(filename)
    for src_prefix in prefixes:
        if filename.startswith(src_prefix):
            _, relpath = filename.split(src_prefix, 1)
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
                dst_filename = change_prefix(filename, dst_prefix)
                copyfile(filename, dst_filename)
                if filename.endswith('.pyc'):
                    pyfile = filename[:-1]
                    if os.path.exists(pyfile):
                        copyfile(pyfile, dst_filename[:-1])
    finally:
        sys.path = _prev_sys_path

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
    else:
        prefix = sys.prefix
    mkdir(lib_dir)
    fix_lib64(lib_dir)
    stdlib_dirs = [os.path.dirname(os.__file__)]
    if sys.platform == 'win32':
        stdlib_dirs.append(join(os.path.dirname(stdlib_dirs[0]), 'DLLs'))
    elif sys.platform == 'darwin':
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
    else:
        if os.path.exists(site_packages_filename):
            logger.info('Deleting %s' % site_packages_filename)
            os.unlink(site_packages_filename)

    if is_pypy or is_win:
        stdinc_dir = join(prefix, 'include')
    else:
        stdinc_dir = join(prefix, 'include', py_version + abiflags)
    if os.path.exists(stdinc_dir):
        copyfile(stdinc_dir, inc_dir)
    else:
        logger.debug('No include dir %s' % stdinc_dir)

    # pypy never uses exec_prefix, just ignore it
    if sys.exec_prefix != prefix and not is_pypy:
        if sys.platform == 'win32':
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
        if sys.platform == 'cygwin' and os.path.exists(executable + '.exe'):
            # Cygwin misreports sys.executable sometimes
            executable += '.exe'
            py_executable += '.exe'
            logger.info('Executable actually exists in %s' % executable)
        shutil.copyfile(executable, py_executable)
        make_exe(py_executable)
        if sys.platform == 'win32' or sys.platform == 'cygwin':
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

            if sys.platform == 'win32':
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
            call_subprocess(
                ["install_name_tool", "-change",
                 os.path.join(prefix, 'Python'),
                 '@executable_path/../.Python',
                 py_executable])
        except:
            logger.fatal(
                "Could not call install_name_tool -- you must have Apple's development tools installed")
            raise

        # Some tools depend on pythonX.Y being present
        py_executable_version = '%s.%s' % (
            sys.version_info[0], sys.version_info[1])
        if not py_executable.endswith(py_executable_version):
            # symlinking pythonX.Y > python
            pth = py_executable + '%s.%s' % (
                    sys.version_info[0], sys.version_info[1])
            if os.path.exists(pth):
                os.unlink(pth)
            os.symlink('python', pth)
        else:
            # reverse symlinking python -> pythonX.Y (with --python)
            pth = join(bin_dir, 'python')
            if os.path.exists(pth):
                os.unlink(pth)
            os.symlink(os.path.basename(py_executable), pth)

    if sys.platform == 'win32' and ' ' in py_executable:
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
        if sys.platform == 'win32':
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

    return py_executable

def install_activate(home_dir, bin_dir, prompt=None):
    home_dir = os.path.abspath(home_dir)
    if sys.platform == 'win32' or is_jython and os._name == 'nt':
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
        assert os.path.basename(lib_parent) == 'lib', (
            "Unexpected parent dir: %r" % lib_parent)
        copyfile(lib_parent, os.path.join(os.path.dirname(lib_parent), 'lib64'))

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
    activate = "import os; activate_this=os.path.join(os.path.dirname(os.path.realpath(__file__)), 'activate_this.py'); execfile(activate_this, dict(__file__=activate_this)); del os, activate_this"
    if sys.platform == 'win32':
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
        lines = [new_shebang+'\n', activate+'\n'] + lines[1:]
        f = open(filename, 'wb')
        f.write('\n'.join(lines).encode('utf-8'))
        f.close()

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
    f = open(filename, 'rb')
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
BKYAg5zZqfYArFEI/g9Yl+sB
""")

##file ez_setup.py
EZ_SETUP_PY = convert("""
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
BDaonX65d/fwEjNqlDjLVIvM9X+XVxF7
""")

##file distribute_setup.py
DISTRIBUTE_SETUP_PY = convert("""
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
cXk3m/wXE179QA==
""")

##file activate.sh
ACTIVATE_SH = convert("""
eJytVVFvokAQfudXTLEP2pw1fW3jg01NNGm1KV4vd22zrDDIJrhrYJHay/33m0VEKGpyufIg7s63
M9/OfDO0YBaKBAIRISzTRMMcIU3Qh0zoEOxEpbGHMBeyxz0t1lyjDRdBrJYw50l4YbVgo1LwuJRK
Q5xKEBp8EaOno41l+bg7Be0O/LaAnhbEmKAGFfmAci1iJZcoNax5LPg8wiRHiQBeoCvBPmfT+zv2
PH6afR/cs8fBbGTDG9yADlHmSPOY7f4haInA95WKdQ4s91JpeDQO5fZAnKTxczaaTkbTh+EhMqWx
QWl/rEGsNJ2kV0cRySKleRGTUKWUVB81pT+vD3Dpw0cSfoMsFF4IIV8jcHqRyVPLpTHrkOu89IUr
EoDHo4gkoBUsiAFVlP4FKjaLFSeNFEeTS4AfJBOV6sKshVwUbmpAkyA4N8kFL+RygQlkpDfum58N
GO1QWNLFipij/yn1twOHit5V29UvZ8Seh0/OeDo5kPz8at24lp5jRXSuDlXPuWqUjYCNejlXJwtV
mHcUtpCddTh53hM7I15EpA+2VNLHRMep6Rn8xK0FDkYB7ABnn6J3jWnXbLvQfyzqz61dxDFGVP1a
o1Xasx7bsipU+zZjlSVjtlUkoXofq9FHlMZtDxaLCrrH2O14wiaDhyFj1wWs2qIl773iTbZohyza
iD0TUQQBF5HZr6ISgzKKNZrD5UpvgO5FwoT2tgkIMec+tcYm45sO+fPytqGpBy75aufpTG/gmhRb
+u3AjQtC5l1l7QV1dBAcadt+7UhFGpXONprZRviAWtbY3dgZ3N4P2ePT9OFxdjJiruJSuLk7+31f
x60HKiWc9eH9SBc04XuPGCVYce1SXlDyJcJrjfKr7ebSNpEaQVpg+l3wiAYOJZ9GCAxoR9JMWAiv
+IyoWBSfhOIIIoRar657vSzLLj9Q0xRZX9Kk6SUq0BmPsceNl179Mi8Vii65Pkj21XXf4MAlSy/t
Exft7A8WX4/iVRkZprZfNK2/YFL/55T+9wm9m86Uhr8A0Hwt
""")

##file activate.fish
ACTIVATE_FISH = convert("""
eJyVVWFv2jAQ/c6vuBoqQVWC9nVSNVGVCaS2VC2rNLWVZZILWAs2sx1Yq/342SEJDrjbmgpK7PP5
3bt3d22YLbmGlGcIq1wbmCPkGhPYcrMEEsGciwGLDd8wg1HK9ZLAWarkCtzvM+gujVl/Hgzcm15i
lkVSLXqtNrzKHGImhDSgcgHcQMIVxiZ7bbXSXFiPUkCClWuAfgJk9MvabbgyOctQbICJBBSaXAkw
EoRUK5ZBcQ3Yba6kWKEwpAX2aVtLjQZklvibsGGKs3mGurDiKRi0YfYFkA6dXl/Rx8n97Nvwmt4N
Z2MChZF7nKv+4he4ZTi2bNohhA1QJP+69ftsPL0dT29G5Pjqeu8QQL3xdxhNswrMO4i+Th7G9O5+
enM3o9PH0f395MrDVKVMu1tcsunaimBtggBCrmrDCLpWZAsu6pXqWSsuTAqklod3z7N4Nm1ydGQP
i9q80xCwMnT4DWudz6EXDil4vMFYGWBF7uj2sUEk6TC12Dx9eiFwcgFESJHYZZU7feMeeBseMEuh
2jsJo9nXRY3DfWxZ5cLh4EphxjZNeXvF1Ly91aoU5YEHQqn3SinZmx2JGTqFpBs1QTre8QGll5Nb
eju8GVlPpXkN1xOypcuutHb/oP8TDkQahuAVQsgefS8FUbW835o46dXkYXh5PSrVWXUOl3jX9jSw
OhHAhTbIEpCp7UOupTiuXR9aoEDlaDZLhJ1cor1O2qBtZoq9OLd5sjnydLV3z3RhU78HFRgulqNC
OTwbqJa9vkJFclQgZSjFFHAwpeIWhe2+h2HYANkKk3PYouv3IDeoFE9wd1TmCuRW7OgJ1bVXGHc7
z5WDL/WW36v2oi37CyVBak61+yPBA9C1qqGxzKQqZ0oPuocU9hpud0PIp8sDHkXR1HKktlzjuUWA
a0enFUyzOWZA4yXGP+ZMI3Tdt2OuqU/SO4q64526cPE0A7ZyW2PMbWZiZ5HamIZ2RcCKLXhcDl2b
vXL+eccQoRze2+02ekPDEtxEsVwNtEzNlikcMOdp8A7BT6f65VSDY9kjtD+HeZbb9C+5wZ4XZ9dC
CQXc+2A6MNP4DqLuqe7t0v4/gA5wfBRGKQGX6oMhUbWv0Bg8uLXoVn8AkYzUxg==
""")

##file activate.csh
ACTIVATE_CSH = convert("""
eJx9U11vmzAUffevOCVRu+UB9pws29Kl0iq1aVWllaZlcgxciiViItsQdb9+xiQp+dh4QOB7Pu49
XHqY59IgkwVhVRmLmFAZSrGRNkdgykonhFiqSCRW1sJSmJg8wCDT5QrucRCyHn6WFRKhVGmhKwVp
kUpNiS3emup3TY6XIn7DVNQyJUwlrgthJD6n/iCNv72uhCzCpFx9CRkThRQGKe08cWXJ9db/yh/u
pvzl9mn+PLnjj5P5D1yM8QmXlzBkSdXwZ0H/BBc0mEo5FE5qI2jKhclHOOvy9HD/OO/6YO1mX9vx
sY0H/tPIV0dtqel0V7iZvWyNg8XFcBA0ToEqVeqOdNUEQFvN41SumAv32VtJrakQNSmLWmgp4oJM
yDoBHgoydtoEAs47r5wHHnUal5vbJ8oOI+9wI86vb2d8Nrm/4Xy4RZ8R85E4uTZPB5EZPnTaaAGu
E59J8BE2J8XgrkbLeXMlVoQxznEYFYY8uFFdxsKQRx90Giwx9vSueHP1YNaUSFG4vTaErNSYuBOF
lXiVyXa9Sy3JdClEyK1dD6Nos9mEf8iKlOpmqSNTZnYjNEWiUYn2pKNB3ttcLJ3HmYYXy6Un76f7
r8rRsC1TpTJj7f19m5sUf/V3Ir+x/yjtLu8KjLX/CmN/AcVGUUo=
""")

##file activate.bat
ACTIVATE_BAT = convert("""
eJyFUkEKgzAQvAfyhz0YaL9QEWpRqlSjWGspFPZQTevFHOr/adQaU1GaUzI7Mzu7ZF89XhKkEJS8
qxaKMMsvboQ+LxxE44VICSW1gEa2UFaibqoS0iyJ0xw2lIA6nX5AHCu1jpRsv5KRjknkac9VLVug
sX9mtzxIeJDE/mg4OGp47qoLo3NHX2jsMB3AiDht5hryAUOEifoTdCXbSh7V0My2NMq/Xbh5MEjU
ZT63gpgNT9lKOJ/CtHsvT99re3pX303kydn4HeyOeAg5cjf2EW1D6HOPkg9NGKhu
""")

##file deactivate.bat
DEACTIVATE_BAT = convert("""
eJxzSE3OyFfIT0vj4spMU0hJTcvMS01RiPf3cYkP8wwKCXX0iQ8I8vcNCFHQ4FIAguLUEgWIgK0q
FlWqXJpcICVYpGzx2BAZ4uHv5+Hv6wq1BWINXBTdKriEKkI1DhW2QAfhttcxxANiFZCBbglQSJUL
i2dASrm4rFz9XLgAwJNbyQ==
""")

##file activate.ps1
ACTIVATE_PS = convert("""
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
QastYw==
""")

##file distutils-init.py
DISTUTILS_INIT = convert("""
eJytV92L4zYQf/dfMU0ottuse7RvC6FQrg8Lxz2Ugz4si9HacqKuIxlJ2ST313dG8odkO9d7aGBB
luZLv/nNjFacOqUtKJMIvzK3cXlhWgp5MDBsqK5SNYftsBAGpLLA4F1oe2Ytl+9wUvW55TswCi4c
KibhbFDSglXQCFmDPXIwtm7FawLRbwtPzg2T9gf4gupKv4GS0N262w7V0NvpbCy8cvTo3eAus6C5
ETU3ICQZX1hFTw/dzR6V/AW1RCN4/XAtbsVXqIXmlVX6liS4lOzEYY9QFB2zx6LfoSNjz1a0pqT9
QOIfJWQ2E888NEVZNqLlZZnvIB0NpHkimlFdKn2iRRY7yGG/CCJb6Iz280d34SFXBS2yEYPNF0Q7
yM7oCjpWvbEDQmnhRwOs6zjThpKE8HogwRAgraqYFZgGZvzmzVh+mgz9vskT3hruwyjdFcqyENJw
bbMPO5jdzonxK68QKT7B57CMRRG5shRSWDTX3dI8LzRndZbnSWL1zfvriUmK4TcGWSnZiEPCrxXv
bM+sP7VW2is2WgWXCO3sAu3Rzysz3FiNCA8WPyM4gb1JAAmCiyTZbhFjWx3h9SzauuRXC9MFoVbc
yNTCm1QXOOIfIn/g1kGMhDUBN72hI5XCBQtIXQw8UEEdma6Jaz4vJIJ51Orc15hzzmu6TdFp3ogr
Aof0c98tsw1SiaiWotHffk3XYCkqdToxWRfTFXqgpg2khcLluOHMVC0zZhLKIomesfSreUNNgbXi
Ky9VRzwzkBneNoGQyyvGjbsFQqOZvpWIjqH281lJ/jireFgR3cPzSyTGWzQpDNIU+03Fs4XKLkhp
/n0uFnuF6VphB44b3uWRneSbBoMSioqE8oeF0JY+qTvYfEK+bPLYdoR4McfYQ7wMZj39q0kfP8q+
FfsymO0GzNlPh644Jje06ulqHpOEQqdJUfoidI2O4CWx4qOglLye6RrFQirpCRXvhoRqXH3sYdVJ
AItvc+VUsLO2v2hVAWrNIfVGtkG351cUMNncbh/WdowtSPtCdkzYFv6mwYc9o2Jt68ud6wectBr8
hYAulPSlgzH44YbV3ikjrulEaNJxt+/H3wZ7bXSXje/YY4tfVVrVmUstaDwwOBLMg6iduDB0lMVC
UyzYx7Ab4kjCqdViEJmDcdk/SKbgsjYXgfMznUWcrtS4z4fmJ/XOM1LPk/iIpqass5XwNbdnLb1Y
8h3ERXSWZI6rZJxKs1LBqVH65w0Oy4ra0CBYxEeuOMbDmV5GI6E0Ha/wgVTtkX0+OXvqsD02CKLf
XHbeft85D7tTCMYy2Njp4DJP7gWJr6paVWXZ1+/6YXLv/iE0M90FktiI7yFJD9e7SOLhEkkaMTUO
azq9i2woBNR0/0eoF1HFMf0H8ChxH/jgcB34GZIz3Qn4/vid+VEamQrOVqAPTrOfmD4MPdVh09tb
8dLLjvh/61lEP4yW5vJaH4vHcevG8agXvzPGoOhhXNncpTr99PTHx6e/UvffFLaxUSjuSeP286Dw
gtEMcW1xKr/he4/6IQ6FUXP+0gkioHY5iwC9Eyx3HKO7af0zPPe+XyLn7fAY78k4aiR387bCr5XT
5C4rFgwLGfMvJuAMew==
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

if __name__ == '__main__':
    main()

## TODO:
## Copy python.exe.manifest
## Monkeypatch distutils.sysconfig
