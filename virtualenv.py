"""Create a "virtual" Python installation
"""

virtualenv_version = "1.5.1"

import base64
import sys
import os
import optparse
import re
import shutil
import logging
import tempfile
import zlib
import distutils.sysconfig
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

join = os.path.join
py_version = 'python%s.%s' % (sys.version_info[0], sys.version_info[1])

is_jython = sys.platform.startswith('java')
is_pypy = hasattr(sys, 'pypy_version_info')

if is_pypy:
    expected_exe = 'pypy-c'
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

if sys.version_info[0] == 2:
    if sys.version_info[:2] >= (2, 6):
        REQUIRED_MODULES.extend(['warnings', 'linecache', '_abcoll', 'abc'])
    if sys.version_info[:2] >= (2, 7):
        REQUIRED_MODULES.extend(['_weakrefset'])
    if sys.version_info[:2] <= (2, 3):
        REQUIRED_MODULES.extend(['sets', '__future__'])
elif sys.version_info[0] == 3:
    # Some extra modules are needed for Python 3, but different ones
    # for different versions.
    REQUIRED_MODULES.extend(['_abcoll', 'warnings', 'linecache', 'abc', 'io',
                             '_weakrefset', 'copyreg', 'tempfile', 'random',
                             '__future__', 'collections', 'keyword', 'tarfile',
                             'shutil', 'struct', 'copy'])
    if sys.version_info[1] == 2:
        REQUIRED_MODULES.append('_abcoll')
    else:
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
            #"_dummy_thread",
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
        >>> l = Logger()
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
            if stop is not None or stop <= consumer_level:
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

def mkdir(path):
    if not os.path.exists(path):
        logger.info('Creating %s', path)
        os.makedirs(path)
    else:
        logger.info('Directory %s already exists', path)

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
    if symlink and hasattr(os, 'symlink'):
        logger.info('Symlinking %s', dest)
        os.symlink(os.path.abspath(src), dest)
    else:
        logger.info('Copying to %s', dest)
        if os.path.isdir(src):
            shutil.copytree(src, dest, True)
        else:
            shutil.copy2(src, dest)

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
        if c != content:
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
        oldmode = os.stat(fn).st_mode & 0xFFF
        newmode = (oldmode | 0x16D) & 0xFFF
        os.chmod(fn, newmode)
        logger.info('Changed mode of %s to %s', fn, oct(newmode))

def _find_file(filename, dirs):
    for dir in dirs:
        if os.path.exists(join(dir, filename)):
            return join(dir, filename)
    return filename

def _install_req(py_executable, unzip=False, distribute=False):
    if not distribute:
        setup_fn = 'setuptools-0.6c11-py%s.egg' % sys.version[:3]
        project_name = 'setuptools'
        bootstrap_script = EZ_SETUP_PY
        source = None
    else:
        setup_fn = None
        source = 'distribute-0.6.15dev.tar.gz'
        project_name = 'distribute'
        bootstrap_script = DISTRIBUTE_SETUP_PY
        try:
            # check if the global Python has distribute installed or plain
            # setuptools
            import pkg_resources
            if not hasattr(pkg_resources, '_distribute'):
                location = os.path.dirname(pkg_resources.__file__)
                logger.notify("A globally installed setuptools was found (in %s)" % location)
                logger.notify("Use the --no-site-packages option to use distribute in "
                              "the virtualenv.")
        except ImportError:
            pass

    search_dirs = file_search_dirs()

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
            os.chdir(os.path.dirname(source))
            # in this case, we want to be sure that PYTHONPATH is unset (not
            # just empty, really unset), else CPython tries to import the
            # site.py that it's in virtualenv_support
            remove_from_env.append('PYTHONPATH')
        else:
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

def install_setuptools(py_executable, unzip=False):
    _install_req(py_executable, unzip)

def install_distribute(py_executable, unzip=False):
    _install_req(py_executable, unzip, distribute=True)

_pip_re = re.compile(r'^pip-.*(zip|tar.gz|tar.bz2|tgz|tbz)$', re.I)
def install_pip(py_executable):
    filenames = []
    for dir in file_search_dirs():
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
    cmd = [py_executable, join(os.path.dirname(py_executable), easy_install_script), filename]
    if filename == 'pip':
        logger.info('Installing pip from network...')
    else:
        logger.info('Installing %s' % os.path.basename(filename))
    logger.indent += 2
    def _filter_setup(line):
        return filter_ez_setup(line, 'pip')
    try:
        call_subprocess(cmd, show_stdout=False,
                        filter_stdout=_filter_setup)
    finally:
        logger.indent -= 2

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

def main():
    parser = optparse.OptionParser(
        version=virtualenv_version,
        usage="%prog [OPTIONS] DEST_DIR")

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
        'VIRTUALENV_USE_DISTRIBUTE to make it the default ')

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

    create_environment(home_dir, site_packages=not options.no_site_packages, clear=options.clear,
                       unzip_setuptools=options.unzip_setuptools,
                       use_distribute=options.use_distribute or sys.version_info[0] > 2,
                       prompt=options.prompt)
    if 'after_install' in globals():
        after_install(options, home_dir)

def call_subprocess(cmd, show_stdout=True,
                    filter_stdout=None, cwd=None,
                    raise_on_returncode=True, extra_env=None,
                    remove_from_env=None):
    cmd_parts = []
    for part in cmd:
        if len(part) > 40:
            part = part[:30]+"..."+part[-5:]
        if ' ' in part or '\n' in part or '"' in part or "'" in part:
            part = '"%s"' % part.replace('"', '\\"')
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
        while 1:
            line = stdout.readline().decode(encoding)
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


def create_environment(home_dir, site_packages=True, clear=False,
                       unzip_setuptools=False, use_distribute=False,
                       prompt=None):
    """
    Creates a new environment in ``home_dir``.

    If ``site_packages`` is true (the default) then the global
    ``site-packages/`` directory will be on the path.

    If ``clear`` is true (default False) then the environment will
    first be cleared.
    """
    home_dir, lib_dir, inc_dir, bin_dir = path_locations(home_dir)

    py_executable = os.path.abspath(install_python(
        home_dir, lib_dir, inc_dir, bin_dir,
        site_packages=site_packages, clear=clear))

    install_distutils(home_dir)

    if use_distribute or os.environ.get('VIRTUALENV_USE_DISTRIBUTE'):
        install_distribute(py_executable, unzip=unzip_setuptools)
    else:
        install_setuptools(py_executable, unzip=unzip_setuptools)

    install_pip(py_executable)

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
    elif is_jython:
        lib_dir = join(home_dir, 'Lib')
        inc_dir = join(home_dir, 'Include')
        bin_dir = join(home_dir, 'bin')
    elif is_pypy:
        lib_dir = home_dir
        inc_dir = join(home_dir, 'include')
        bin_dir = join(home_dir, 'bin')
    else:
        lib_dir = join(home_dir, 'lib', py_version)
        inc_dir = join(home_dir, 'include', py_version)
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
                if fn != 'site-packages' and os.path.splitext(fn)[0] in REQUIRED_FILES:
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

    if is_pypy:
        stdinc_dir = join(prefix, 'include')
    else:
        stdinc_dir = join(prefix, 'include', py_version)
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
        if is_pypy:
            # make a symlink python --> pypy-c
            python_executable = os.path.join(os.path.dirname(py_executable), 'python')
            logger.info('Also created executable %s' % python_executable)
            copyfile(py_executable, python_executable)

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

    if 'Python.framework' in prefix:
        logger.debug('MacOSX Python framework detected')

        # Make sure we use the the embedded interpreter inside
        # the framework, even if sys.executable points to
        # the stub executable in ${sys.prefix}/bin
        # See http://groups.google.com/group/python-virtualenv/
        #                              browse_thread/thread/17cab2f85da75951
        original_python = os.path.join(
            prefix, 'Resources/Python.app/Contents/MacOS/Python')
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
    cmd = [py_executable, '-c', 'import sys; print(sys.prefix)']
    logger.info('Testing executable with %s %s "%s"' % tuple(cmd))
    proc = subprocess.Popen(cmd,
                            stdout=subprocess.PIPE)
    proc_stdout, proc_stderr = proc.communicate()
    proc_stdout = proc_stdout.strip().decode(sys.getdefaultencoding())
    proc_stdout = os.path.normcase(os.path.abspath(proc_stdout))
    if proc_stdout != os.path.normcase(os.path.abspath(home_dir)):
        logger.fatal(
            'ERROR: The executable %s is not functioning' % py_executable)
        logger.fatal(
            'ERROR: It thinks sys.prefix is %r (should be %r)'
            % (proc_stdout, os.path.normcase(os.path.abspath(home_dir))))
        logger.fatal(
            'ERROR: virtualenv is not compatible with this system or executable')
        if sys.platform == 'win32':
            logger.fatal(
                'Note: some Windows users have reported this error when they installed Python for "Only this user".  The problem may be resolvable if you install Python "For all users".  (See https://bugs.launchpad.net/virtualenv/+bug/352844)')
        sys.exit(100)
    else:
        logger.info('Got sys.prefix result: %r' % proc_stdout)

    pydistutils = os.path.expanduser('~/.pydistutils.cfg')
    if os.path.exists(pydistutils):
        logger.notify('Please make sure you remove any previous custom paths from '
                      'your %s file.' % pydistutils)
    ## FIXME: really this should be calculated earlier
    return py_executable

def install_activate(home_dir, bin_dir, prompt=None):
    if sys.platform == 'win32' or is_jython and os._name == 'nt':
        files = {'activate.bat': ACTIVATE_BAT,
                 'deactivate.bat': DEACTIVATE_BAT}
        if os.environ.get('OS') == 'Windows_NT' and os.environ.get('OSTYPE') == 'cygwin':
            files['activate'] = ACTIVATE_SH
    else:
        files = {'activate': ACTIVATE_SH}

        # suppling activate.fish in addition to, not instead of, the
        # bash script support.
        files['activate.fish'] = ACTIVATE_FISH

        # same for csh/tcsh support...
        files['activate.csh'] = ACTIVATE_CSH



    files['activate_this.py'] = ACTIVATE_THIS
    vname = os.path.basename(os.path.abspath(home_dir))
    for name, content in files.items():
        content = content.replace('__VIRTUAL_PROMPT__', prompt or '')
        content = content.replace('__VIRTUAL_WINPROMPT__', prompt or '(%s)' % vname)
        content = content.replace('__VIRTUAL_ENV__', os.path.abspath(home_dir))
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
        sys.exit(3)
    return exe

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
    activate = "import os; activate_this=os.path.join(os.path.dirname(__file__), 'activate_this.py'); execfile(activate_this, dict(__file__=activate_this)); del os, activate_this"
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
        lines = f.readlines()
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
        f.writelines(lines)
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
    link = f.read().strip()
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
/wMj5/XF
""")

##file ez_setup.py
EZ_SETUP_PY = convert("""
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
dan02KxXO91yZ/N4jSY1SpxlqkX1599V/jg7
""")

##file distribute_setup.py
DISTRIBUTE_SETUP_PY = convert("""
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
""")

##file activate.sh
ACTIVATE_SH = convert("""
eJytVU1v4jAQPW9+xTT0ANVS1GsrDlRFAqmFqmG72m0rY5IJsRRslDiktNr/vuMQ8tFQpNU2B4I9
H36eeW/SglkgYvBFiLBKYg0LhCRGD1KhA7BjlUQuwkLIHne12HCNNpz5kVrBgsfBmdWCrUrA5VIq
DVEiQWjwRISuDreW5eE+CtodeLeAnhZEGKMGFXqAciMiJVcoNWx4JPgixDjzEj48QVeCfcqmtzfs
cfww+zG4ZfeD2ciGF7gCHaDMPM1jtvuHXAsPfF2rSGeOxV4iDY5GUGb3xVEYv2aj6WQ0vRseAlMY
G5DKsAawwnQUXt2LQOYlzZoYByqhonqoqfxZf4BLD97i4DukgXADCPgGgdOLTK5arYxZB1xnrc9T
EQFcHoZEAa1gSQioo/TPV5FZrDlxJA+NzwF+Ek1UonOzFnKZp6k5mgLBqSkuuAGXS4whJb5xz/xs
wXCHjiVerAk5eh9Kfz1wqOldtVv9dkbscfjgjKeTA8XPrtaNauX5rInOxaHuOReNtpFjo1/OxdFG
5eY9hJ3L3jqcPJbATggXAemDLZX0MNZRYjSDH7C1wMHQh73DyYfTu8a0F9v+6D8W6XNnF1GEIXW/
JrSKPOtnW1YFat9mrLJkzLbyIlTvYzV0RGXcaTBfVLx7jF2PJ2wyuBsydpm7VSVa4C4Zb6pFO2TR
huypCEPwuQjNftUrNl6GsYZzuFrrLdC9iJjQ3omAPBbcI2lsU77tUD43kw1NPZhTrnZWzuQKLomx
Rd4OXM1ByExVVkmoTwfBJ7Lt10Iq1Kgo23Bmd8Ib1KrGbsbO4Pp2yO4fpnf3s6MnZiwuiJuls1/L
Pu4yUCvhpA+vZaJvWWDTr0yFYYyVnHMqCEq+QniuYX225xmnzRENjbXACF3wkCYNVZ1mBwxoR9Iw
WAo3/36oSOTfgjwEEQKt15e9Xpqm52+oaXxszmnE9GLl65RH2OMmS6+u5acKxDmlPgj2eT5/gQOX
LLK0j1y0Uwbmn438VZkVpqlfNKa/YET/53j+99G8H8tUhr9ZSXs2
""")

##file activate.fish
ACTIVATE_FISH = convert("""
eJydVm1v4jgQ/s6vmA1wBxUE7X2stJVYlVWR2lK13d6d9laRk0yIr8HmbIe0++tvnIQQB9pbXT5A
Ys/LM55nZtyHx5RrSHiGsMm1gRAh1xhDwU0Kng8hFzMWGb5jBv2E69SDs0TJDdj3MxilxmzPZzP7
pVPMMl+q9bjXh1eZQ8SEkAZULoAbiLnCyGSvvV6SC7IoBcS4Nw0wjcFbvJDcjiuTswzFDpiIQaHJ
lQAjQUi1YRmUboC2uZJig8J4PaCnT5IaDcgsbm/CjinOwgx1KcUTMEhhTgV4g2B1fRk8Le8fv86v
g7v545UHpZB9rKnp+gXsMhxLunIIpwVQxP/l9c/Hq9Xt1epm4R27bva6AJqN92G4YhbMG2i+LB+u
grv71c3dY7B6WtzfLy9bePbp0taDTXSwJQJszUnnp0y57mvpPcrF7ZODyhswtd59+/jdgw+fwBNS
xLSscksUPIDqwwNmCez3PpxGeyBYg6HE0YdcWBxcKczYzuVJi5Wu915vn5oWePCCoPUZBN5B7IgV
MCi54ZDLG7TUZ0HweXkb3M5vFmSpFm/gthhBx0UrveoPpv9AJ9unIbQYdUoe21bKg2q48sPFGVwu
H+afrxd1qvclaNlRFyh1EQ2sSccEuNAGWQwysfVpz1tPajUqbqJUnEcIJkWo6OXDaodK8ZiLdbmM
L1wb+9H0D+pcyPSrX5u5kgWSygRYXCnJUi/KKcuU4cqsAyTKZBiissLc7NFwizvjxtieKBVCIdWz
fzilzPaYyljZN0cGN1v7NnaIPNCGmVy3GKuJaQ6iVjE1Qfm+36hglErwmnAD8hu0dDy4uICBA8ZV
pQr/q/+O0KFW2kjelu9Dgb9SDBsWV4F4x5CswgS0zBVlk5tDMP5bVtUGpslbm81Lu2sdKq7uNMGh
MVQ4fy9xhogC1lS5guhISa0DlBWv0O8odT6/LP+4WZzDV6FzIkEqC0uolGZSZoMnlpxplmD2euaT
O4hkTpPnbztDccey0bhjDaBIqaWQa0uwEtQEwtyU56i4fq54F9IE3ORR6mKriODM4XOYZwaVYLYz
7SPbKkz4i7VkB6/Ot1upDE3znNqYKpM8raa0Bx8vfvntJ32UENsM4aI6gJL+jJwhxhh3jVIDOcpi
m0r2hmEtS8XXXNBk71QCDXTBNhhPiHX2LtHkrVIlhoEshH/EZgdq53Eirqs5iFKMnkOmqZTtr3Xq
djvPTWZT4S3NT5aVLgurMPUWI07BRVYqkQrmtCKohNY8qu9EdACoT6ki0a66XxVF4f9AQ3W38yO5
mWmZmIIpnDFrbXakvKWeZhLwhvrbUH8fahhqD0YUcBDJjEBMQwiznE4y5QbHrbhHBOnUAYzb2tVN
jJa65e+eE2Ya30E2GurxUP8ssA6e/wOnvo3V78d3vTcvMB3n7l3iX1JXWqk=
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
eJyNUlGL2zAMfvevEBlHEujSsXsL9GGDvW1jD3sZpQQ3Ua7aJXawnbT595Ocpe0dO5ghseVP+vRJ
VpIkn2cYPZknwAvWLXWYhRP5Sk4baKgOWRWNqtpdgTyH2Y5wpq5Tug406YAgKEzkwqg7NBPwR86a
Hk0olPopaK0NHJHzYQPnE5rI0o8+yBUwiBfyQcT8mMPJGiAT0A0O+b8BY4MKJ7zPcSSzHaKrSpJE
qeDmUgGvVbPCS41DgO+6xy/OWbfAThMn/OQ9ukDWRCSLiKzk1yrLjWapq6NnvHUoHXQ4bYPdrsVX
4lQMc/q6ZW975nmSK+oH6wL42a9H65U6aha342Mh0UVDzrD87C1bH73s16R5zsStkBZDp0NrXQ+7
HaRnMo8f06UBnljKoOtn/YT+LtdvSyaT/BtIv9KR60nF9f3qmuYKO4//T9ItJMsjPfgUHqKwCZ3n
xu/Lx8M/UvCLTxW7VULHxB1PRRbrYfvWNY5S8it008jOjcleaMqVBDnUXcWULV2YK9JEQ92OfC96
1Tv4ZicZZZ7GpuEpZbbeQ7DxquVx5hdqoyFSSmXwfC90f1Dc7hjFs/tK99I0fpkI8zSLy4tSy+sI
3vMWehjQNJmE5VePlZbL61nzX3S93ZcfDqznnkb9AZ3GWJU=
""")

if __name__ == '__main__':
    main()

## TODO:
## Copy python.exe.manifest
## Monkeypatch distutils.sysconfig
