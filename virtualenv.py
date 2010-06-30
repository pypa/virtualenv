#!/usr/bin/env python
"""Create a "virtual" Python installation
"""

virtualenv_version = "1.4.8-pypy"

import sys
import os
import optparse
import re
import shutil
import logging
import distutils.sysconfig
try:
    import subprocess
except ImportError, e:
    if sys.version_info <= (2, 3):
        print 'ERROR: %s' % e
        print 'ERROR: this script requires Python 2.4 or greater; or at least the subprocess module.'
        print 'If you copy subprocess.py from a newer version of Python this script will probably work'
        sys.exit(101)
    else:
        raise
try:
    set
except NameError:
    from sets import Set as set

join = os.path.join

is_jython = sys.platform.startswith('java')
is_pypy = hasattr(sys, 'pypy_version_info')

if is_pypy:
    py_version = 'pypy%s.%s' % (sys.pypy_version_info[0], sys.pypy_version_info[1])
    expected_exe = 'pypy-c'
else:
    py_version = 'python%s.%s' % (sys.version_info[0], sys.version_info[1])
    expected_exe = 'python'


expected_exe = is_jython and 'jython' or expected_exe

REQUIRED_MODULES = ['os', 'posix', 'posixpath', 'nt', 'ntpath', 'genericpath',
                    'fnmatch', 'locale', 'encodings', 'codecs',
                    'stat', 'UserDict', 'readline', 'copy_reg', 'types',
                    're', 'sre', 'sre_parse', 'sre_constants', 'sre_compile',
                    'zlib']

REQUIRED_FILES = ['lib-dynload', 'config']

if sys.version_info[:2] >= (2, 6):
    REQUIRED_MODULES.extend(['warnings', 'linecache', '_abcoll', 'abc'])
if sys.version_info[:2] <= (2, 3):
    REQUIRED_MODULES.extend(['sets', '__future__'])
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
        f.write(content)
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
            f.write(content)
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
        oldmode = os.stat(fn).st_mode & 07777
        newmode = (oldmode | 0555) & 07777
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
        source = 'distribute-0.6.8.tar.gz'
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
        import tempfile
        fd, ez_setup = tempfile.mkstemp('.py')
        os.write(fd, bootstrap_script)
        os.close(fd)
        cmd = [py_executable, ez_setup]
    else:
        cmd = [py_executable, '-c', bootstrap_script]
    if unzip:
        cmd.append('--always-unzip')
    env = {}
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
        cwd = '/tmp'
        if source is not None and os.path.exists(source):
            # the current working dir is hostile, let's copy the
            # tarball to /tmp
            target = os.path.join(cwd, os.path.split(source)[-1])
            shutil.copy(source, target)
    try:
        call_subprocess(cmd, show_stdout=False,
                        filter_stdout=_filter_ez_setup,
                        extra_env=env,
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
    filenames.sort(key=lambda x: os.path.basename(x).lower())
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
        help='Use Distribute instead of Setuptools. Set environ variable'
        'VIRTUALENV_USE_DISTRIBUTE to make it the default ')

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
            os.execvpe(interpreter, [interpreter, file] + sys.argv[1:], env)

    if not args:
        print 'You must provide a DEST_DIR'
        parser.print_help()
        sys.exit(2)
    if len(args) > 1:
        print 'There must be only one argument: DEST_DIR (you gave %s)' % (
            ' '.join(args))
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
                       use_distribute=options.use_distribute)
    if 'after_install' in globals():
        after_install(options, home_dir)

def call_subprocess(cmd, show_stdout=True,
                    filter_stdout=None, cwd=None,
                    raise_on_returncode=True, extra_env=None):
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
    if extra_env:
        env = os.environ.copy()
        env.update(extra_env)
    else:
        env = None
    try:
        proc = subprocess.Popen(
            cmd, stderr=subprocess.STDOUT, stdin=None, stdout=stdout,
            cwd=cwd, env=env)
    except Exception, e:
        logger.fatal(
            "Error %s while executing command %s" % (e, cmd_desc))
        raise
    all_output = []
    if stdout is not None:
        stdout = proc.stdout
        while 1:
            line = stdout.readline()
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
                       unzip_setuptools=False, use_distribute=False):
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

    install_activate(home_dir, bin_dir)

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
                print 'Error: the path "%s" has a space in it' % home_dir
                print 'To handle these kinds of paths, the win32api module must be installed:'
                print '  http://sourceforge.net/projects/pywin32/'
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
        inc_dir = join(home_dir, 'Include')
        bin_dir = join(home_dir, 'bin')
    else:
        lib_dir = join(home_dir, 'lib', py_version)
        inc_dir = join(home_dir, 'include', py_version)
        bin_dir = join(home_dir, 'bin')
    return home_dir, lib_dir, inc_dir, bin_dir


def change_prefix(filename, dst_prefix):
    prefixes = [sys.prefix]
    if hasattr(sys, 'real_prefix'):
        prefixes.append(sys.real_prefix)
    prefixes = map(os.path.abspath, prefixes)
    filename = os.path.abspath(filename)
    for src_prefix in prefixes:
        if filename.startswith(src_prefix):
            _, relpath = filename.split(src_prefix, 1)
            assert relpath[0] == '/'
            relpath = relpath[1:]
            return join(dst_prefix, relpath)
    assert False, "Filename %s does not start with any of these prefixes: %s" % \
        (filename, prefixes)

def copy_required_modules(dst_prefix):
    for modname in REQUIRED_MODULES:
        if modname in sys.builtin_module_names:
            logger.notify("Ignoring built-in bootstrap module: %s" % mod)
            continue
        try:
            mod = __import__(modname)
        except ImportError:
            logger.notify("Cannot import bootstrap module: %s" % modname)
        else:
            filename = mod.__file__
            if getattr(mod, '__path__', None) is not None:
                assert filename.endswith('__init__.py') or \
                       filename.endswith('__init__.pyc') or \
                       filename.endswith('__init__$py.class')
                filename = os.path.dirname(filename)
            dst_filename = change_prefix(filename, dst_prefix)
            copyfile(filename, dst_filename)
            if filename.endswith('.pyc'):
                pyfile = filename[:-1]
                if os.path.exists(pyfile):
                    copyfile(pyfile, dst_filename[:-1])


def install_python(home_dir, lib_dir, inc_dir, bin_dir, site_packages, clear):
    """Install just the base environment, no distutils patches etc"""
    if sys.executable.startswith(bin_dir):
        print 'Please use the *system* python to run this script'
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

    stdinc_dir = join(prefix, 'include', py_version)
    if os.path.exists(stdinc_dir):
        copyfile(stdinc_dir, inc_dir)
    else:
        logger.debug('No include dir %s' % stdinc_dir)

    if sys.exec_prefix != prefix:
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
        shutil.copy(
                os.path.join(
                    prefix, 'Resources/Python.app/Contents/MacOS/%s' % os.path.basename(sys.executable)),
                py_executable)

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
    cmd = [py_executable, '-c', 'import sys; print sys.prefix']
    logger.info('Testing executable with %s %s "%s"' % tuple(cmd))
    proc = subprocess.Popen(cmd,
                            stdout=subprocess.PIPE)
    proc_stdout, proc_stderr = proc.communicate()
    proc_stdout = os.path.normcase(os.path.abspath(proc_stdout.strip()))
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

def install_activate(home_dir, bin_dir):
    if sys.platform == 'win32' or is_jython and os._name == 'nt':
        files = {'activate.bat': ACTIVATE_BAT,
                 'deactivate.bat': DEACTIVATE_BAT}
        if os.environ.get('OS') == 'Windows_NT' and os.environ.get('OSTYPE') == 'cygwin':
            files['activate'] = ACTIVATE_SH
    else:
        files = {'activate': ACTIVATE_SH}
    files['activate_this.py'] = ACTIVATE_THIS
    for name, content in files.items():
        content = content.replace('__VIRTUAL_ENV__', os.path.abspath(home_dir))
        content = content.replace('__VIRTUAL_NAME__', os.path.basename(os.path.abspath(home_dir)))
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
    activate_this = os.path.join(home_dir, 'bin', 'activate_this.py')
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
    bin_dir = os.path.join(home_dir, 'bin')
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

##file site.py
SITE_PY = """
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
gQU5sVNt+a0xCP4PyWGp0g==
""".decode("base64").decode("zlib")

##file ez_setup.py
EZ_SETUP_PY = """
eJzNWmuP28YV/a5fwShYSIJlLt8PGXKRJi5gIEiDPAoU9lY7zxVrilRJyhu1yH/vmeFDJLVU2iIf
ysDZXXJ45z7PuXekL784nqt9ns3m8/kf87wqq4IcjVJUp2OV52lpJFlZkTQlVYJFs/fSOOcn45lk
lVHlxqkUw7XqaWEcCftEnsSirB+ax/Pa+PuprLCApScujGqflDOZpEK9Uu0hhByEwZNCsCovzsZz
Uu2NpFobJOMG4Vy/oDZUa6v8aOSy3qmVv9nMZgYuWeQHQ/xzp+8byeGYF5XScnfRUq8b3lquriwr
xD9OUMcgRnkULJEJMz6LooQT1N6XV9fqd6zi+XOW5oTPDklR5MXayAvtHZIZJK1EkZFKdIsulq71
pgyreG6UuUHPRnk6HtNzkj3NlLHkeCzyY5Go1/OjCoL2w+Pj2ILHR3M2+0m5SfuV6Y2VRGEUJ/xe
KlNYkRy1eU1UtZbHp4LwfhxNlQyzxnnluZx98+5PX/387U+7v7z74cf3f/7O2BpzywyYbc+7Rz//
8K3yq3q0r6rj5v7+eD4mZp1cZl483TdJUd7flff4r9vtfm7cqV3Mxr8fNu7DbHbg/o6TikDgv3TE
Fpc3XmNzar8+nh3TNcXT02JjLKLIcRiRsWU7vsUjL6JxHNBQOj4LRMDIYn1DitdKoWFMIuJZrvB8
y5GURr4QrrRjzw5dn9EJKc5QFz/ww9CPeUQCHknmeVZokZhboRM6PI5vS+l08WAAibgdxNyhIghs
SVyHBMJ3hCcjZ8oid6gLpa7NLMlCN45J4PphHIc+IzyWPrECO7oppdPFjUjEcJcHgnHHcbxQ2mEs
Q06CIJaETUjxhroEjuX5xPEE94QtKAtDKSw3JsQTgQyFf1PKxS+MOsSOfOgRccKkpA63oY/lUpfa
zHtZChvlC3WlQ33fjXmAuIYy9AgPY9uBIBJb0YRFbJwvsIcLDk8GIXe4I6WwPcuK3cCTDvEmIs1s
a6gMgzscQn3uEsvxA88PEB9mu5FlkdCKrdtiOm38kONFxCimkRWGDvNj4rsk8lyX+JxPeqYW47di
uPACwiL4Mg5ZFPt+6AhfRD7SUdCIhbfFBJ02kUAlESGtAA5ymAg824M0B0bC4RPRBqgMfeNQIghq
2HY53kcZOZEIKfGpT6ARF7fFXCLFAzeWMbUgzGOe48Wh5XpcMEcwizmTkbKHvgk8FnvSpTIkIbLQ
FSxyhUUdhDv0YurcFtP5hkoSO7ZlUY4wcdQEJAnOXQQ+8KwomBAzwhlpWYFHZUCIQ0NuQS141kNi
W5EdMmcqUCOcCezAjh0hmOtLLxSImh0wHhDbgVQnnJIywhlpRwAogC+XSBXi+DGLIUXaPKRhJCfQ
io1wRliCh14QOSyOIyppCE9HFrLXQsxDeyrY7jBIhAppB5JzGOb7vu1Fns1C4BePozjwp6SM0Ipa
NLZdmzBCXceCM4BzofQ85gMoQlvelNJZhCSR2DPgnqTSRUVRGXsBs+AqoJ6YShhvaFGk0BrA7zqM
05iFDmXSA3w5gXQiIqfQyh9aJEQseWRBHRQkMla6ApjuhwAMHtnBVKT9oUVEAqu4BKvYoWULAeeG
ICefMhAeCaZQxh/FKOKuDAAIHmOERKHtIXG4G1LGuMt9PiElGFqEgonA8pFtB2CiKPJCByLAmL4X
o7SngDMYsRvzAyL9kMK/6B5QDYEFQzzPRYH5ZAobgqFF1JERCX0HZA/YpS5I2kKoufAlWgnfnZAS
juDOQoxkTDhzSWD7wrdtH2WIliICBE7mSzhiAhLJ2PfAAhxYbkkahEza0kEY8MiZqoBwaJEHjiXA
W4mWAQXouZ5t25KLyLXxL5zSJRp1Q5bqhZwYHok5+EOlIAA8ci3VWFm3pXQWMUrcCNiAnsOLXGap
nEW2wdkMzDJJA9HQIjt07BAgh0DHnNm+5ccW8SPqCtR57E9FOh5aBN2ZZ6GZsZWHqRcHwmOSCiuC
rcyainQ8QgYkGRo7cKsbRTwAOhEhrADgxQLXm+rvGimdRVIgtK7wiR1S22EIE/M9m4bgXjC/mGKS
eMhHjKBsbKlQkziCA5js2AWzhdSPHfQ4kPLrrDcRYLwpZ1Vx3tQD156U+zSh7byF3n0mfmECo8Z7
feedGomatXjYXzfjQhq7zyRN0O2LHW4todMuwzy4NtQAsNpoAxJptPfVzNiOB/VDdfEEs0WFcUGJ
0C+ae/FLfRfzXbsMcpqVX2w7KR9a0Q8XeerC3IVp8O1bNZ2UFRcF5rrlYIW65sqkxoJmPrzDFEYw
hvEvDGP5fV6WCU174x9GOvx9+MNqfiXsrjNz8Gg1+EvpI35JqqVT3y8Q3CLT7qodOhoO9aJmvNqO
hrl1p9aOklJsewPdGpPiDqPqNi9NdirwW51M3QtcpOS8tf1ZEySMjV+dqvwAPzBMl2eMohm/78zu
nRSouf5APiGWGJ4/w1VEOQjOU6YdSbWvx/nHRulHo9znp5SraZbUvu5Layfz7HSgojCqPakMDMKd
YC1LTcCZ8q4hMfV2Sp0yrl8RxuPAEY+GGmmXz/uE7dvdBbRWRxO1PGNxv1iZULL20qPaUsnpHWPs
RTE4IHlOMHPTSyYIvkZG1gmuVc5y+CMtBOHni/rY473sqafdrrdrzia0mKrRUkujQqvSOESfWLA8
42Xtm1aNI0GiKKfCI6qskipB6LKn3nlGHfHG/jwT+jyhPhvhtV5wap4qH754PqK0bA4bRCNMn+UU
+Qk7iVqVus6IcRBlSZ5EfcBxKbrHR50vBUlKYfx4LitxePeL8ldWByIzSIV79ckGoQpalPEqBZUx
9amH2Wao/vlMyl2NQrB/ayyOn552hSjzU8FEuVAIo7Y/5PyUilKdkvQAdPy4rglUHUceNG5bri5I
olJueymaXl02HhuVYFt261GhXTCgLRITnhVFtbTWapMeyDVA3e30pn+6Q9tjvl0TmJ0G5q2SUQcI
wD6WNXCQfvgCwncvtYDUd0jz6HqHgWizSa7l/KLx2+38VeOq1ZtGdl+FoYC/1Cu/zjOZJqyCazZ9
9O9H/r9F+/lP+0v2T+T78u32rlx1tdzWsD7K/JgNAX/OSLaoVEl1JQLMUMd3ukaa4zpVLacsQyqb
xvepQIa0y6/kqRpSpQwAErCl1VAmRQlHnEpVDgtIOLehN17/3FN+YY7kfcw+ZsuvT0UBaYDzWsBd
MeKtFVjrksvCJMVT+cF6uM1ZOn5pKYYxQKIPw7nuV9qHUZ0+qFe+hLUayfNPA1Ev5eB01nyToCQS
elIM/l1e/SkHL9zO55ppXyrr35tuVfGjPAc8+80LpKrLmFxIwUhzVrckGj5rG5KqPiHWLcb/KcnW
EK0+A2hJ9rc4Vt1Tu14TbI37jxfOnODFvGbDlgwVqbDqRNKLEQ3JDImk/YihANdQB9m6RwqldZ61
/erW6IHZ67sSvfddqVrveb9wRkfgda5Cbp87lM+MV8MWsSSfBbTfoiWvSeHveZItWwppl9biyoIp
cbpP/g5s3rbWCqra11GkZVUua7GrjSqwrz7niUqgoyCKL1t1yq4+BniuLp2KHIKUN8rWS2n+NFil
mnEVl+G76sJK85kU2VL5+fXvd9WfkDTA2iB5+VKW3+mUUJ+cLMVnkak/YM4Rys72Ij2qvu99nW29
3qNLFTQnKv/VZztL5YoZKGFtAF1m6tYB5ZwJOBKvoA5V5wuEFs8KjwnG2bLUb/c5QCO4OWu2BHQ3
Pc5lR6jM22w2Z7MlQExslIe1mANhe9Vu8VzUxLRHeKFE9ZwXn5pN18axZpecVqT5XE4hhUaJu3I2
UygCDzDdtesFkHypxKZyCtGwVd8Ac/V7RhFJsb5KmR7oXjVUOsvWqpquXkNHoZO1StRk2TROqRDH
N/WP5aj3GmZnC8OaF8u53mLEe7rkGnww8TM/imx5texL4wc0/ffPRVIBfBBj+Fe328DwT2v10eCz
ip5qF1ihyhDQyPKiOOnkSMVImI57Pz1UF14Jvb7FxPZqPmabGsJhgKkGkuVqqHGNItqaGivW82c6
hzvxwNR21GN49xKGQTUUbsYQgA02eheW5qVYrq4goqw2Wmj/ecNmLWhBwVT90sLW7D+5FH8fkOlL
NCyf11OMfeHc97c+NNUc+w6tVbOqJYiXmunRh9G3Oul6eOiw+kriZc3tAUNP6tZ1SzYcIwZThI6Z
Ko3e7MDywwGGmoMesj3OIc1A1l5NjLSLU3CB9vPqlTpteVjpNH0Wi0KntTAUjf9mqihLlZ9HXKXU
vuYQLDplmAA/LTuzhg1n0m/czd2u8dZuZ2wxElqmZdqL/3pE+CsAXoOrmotpmacCtToxGrdNP8ik
buyvGvpCHPLPGm91JOrvPOgJGMxRAXrT38DdUac+2ZI3RfWPYbPSm7z63c71MPgfDHT4eaP/Hk1t
m+ls/59T8laZdYJ/U8pVNr9Ud225PQxndu1sa4XEh1WK/RE4pjNFPXk5Q9Uuv5MDOvW15jemsDrN
5z9etUXzdYsoc4DgkyaiQh3/IgnRJF0Sev6CvMXyB7RT8/bbOebxPJw+5/X3bq6/mmKuFs2x5rHj
p3aEKS/w/LN+aqgSoackrV7X58QQ+aSGu7NC5H4WF838o3qt9ly5E3txiO65L921+lOtWF66ai2k
5UJNmouCLi7PumNm9e5Dc0QtW1J98ZhadmRXj4A1RX+Yqz/uig3+rYEVGB+aTrNuyNqNTJDvoVyu
HrqXzRIWd9R5VEPFfF5PCjVJ9x2DCGCErNqJQX+faNveNZ9EVRetur/sT+c73THsdk3Wdy5pZKwN
7ZY3TUvUOuDN2NgDqTANbqGnWQpSsP1y/jHrfx/oY7b88LdfH16tfp3r9mTVH2P02z0segGxQeT6
G1mpIRQKfDG/LtIWEWtV8f8PGy3Y1K330l49YAzTjnyln9YPMbri0ebhZfMXz01OyKY96lTvOWAG
M1o/breL3U4V7G636D4FSZVEqKlr+K2j6bD9+4P9gHdev4az6lLp0VevdrrlzubhJV7UGHGRqRbV
178BYnMUkw==
""".decode("base64").decode("zlib")

##file distribute_setup.py
DISTRIBUTE_SETUP_PY = """
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
""".decode("base64").decode("zlib")

##file activate.sh
ACTIVATE_SH = """
eJytVFFv2jAQfs+vuIU+QDWK+tqKB6oigdRC1bBOW1sZk1yIpWAj2yGj0/77ziFAUijStPIA2Hc+
f/7u+64Bk0QYiEWKsMiMhRlCZjCCXNgEfKMyHSLMhOzw0IoVt+jDeazVAmbcJOdeA9Yqg5BLqSzo
TIKwEAmNoU3Xnhfh9hQ0W/DbA/o0QKNBCyqNAOVKaCUXKC2suBZ8lqIpskQMz9CW4J+x8d0texo+
Tr717thDbzLw4RWuwSYoi0z3cdvdY6m7DPy1VNoWibu9TDocB4eKeCxOwvgxGYxHg/F9/xiYXfAA
0v7YAbBd6CS8ehaBLCktmmgSlRGpEVqiv+gPcBnBm0m+Qp6IMIGErxA4/VAoVIuFC9uE26L1ZSkS
QMjTlCRgFcwJAXWU/sVKu8WSk0bKo+YC4DvJRGW2DFsh52WZWqIjCM4cuRAmXM7RQE5645H7WoPT
Dl1LulgScozeUX/TC6jpbbVZ/QwG7Kn/GAzHoyPkF09r6xo9HzUxuDzWveDyoG2UeNCv4PJko8rw
FsImZRvtj572wL4QLgLSBV8qGaGxOnOewXfYGhBgGsM24cu729sutDXb9uo/HvlzExdaY0rdrxmt
Ys/63Z5Xgdr1GassGfO9koTqe7wDHxGNGw+Wi0p2h7Gb4YiNevd9xq7KtKpFd7j3inds0Q5FrBN7
LtIUYi5St1/NMi7LKdZpDhdLuwZ6FwkTmhsTUMaMR2SNdc7XLaoXFrahqQdTqtUs6Myu4YoUu6vb
guspCFm4ytsL6sNB8IFtu7UjFWlUnO00s7nhDWqssdth0Lu567OHx/H9w+TkjYWKd8ItyvlTAo+S
LxBeanVf/GmhP+rsoR8a4EwpeEpTgRgin0OPdiQZdy7CctYrLcq5XR5BhMTa5VWnk+f5xRtasvrq
gsZBx6jY5lxjh7sqnbrvnisQp1T6KNiX6fQV9m/D1GC9SvPEQ1v7g+WIrxjaMf9Js/QT5uh/ztB/
n5/b2Uk0/AXm/2MV
""".decode("base64").decode("zlib")

##file activate.bat
ACTIVATE_BAT = """
eJyFUssKgzAQvAfyD3swYH+hItSiVKlGsalQKOyhauvFHOr/U+MzFcWc9jEzO7vkVLw+EmRZUvIt
GsiCVNydED2e2YhahkgJJVUJtWwgL8qqLnJI0jhKBJiUQPsUv6/YRmJcKDkMlBGOcehOmptctgJj
e2IP4cfcjyNvFOwVp/JSdWqMygq+MthmkwHNojmfhjuRh3iAGffncsPYhpl2mm5sbY+9QzjC7ylt
sFy6LTEL3rKRcLsGicrXV++4HVz1jzN4Vta+BnsingM+nMLSiB53KfkBsnmnEA==
""".decode("base64").decode("zlib")

##file deactivate.bat
DEACTIVATE_BAT = """
eJxzSE3OyFfIT0vj4spMU0hJTcvMS01RiPf3cYkP8wwKCXX0iQ8I8vcNCFHQ4FIAguLUEgWIgK0q
FlWqXJpcICVYpGzx2BAZ4uHv5+Hv6wq1BWINXBTdKriEKkI1DhW2QAfhttcxxANiFZCBbglQSJUL
i2dASrm4rFz9XLgAwJNbyQ==
""".decode("base64").decode("zlib")

##file distutils-init.py
DISTUTILS_INIT = """
eJytV0tv4zYQvutXTG0UktpELdpbAKNAsZcAix6KBXoIAoKRKJuNTAokHdv76ztDyhT18LaHCkjA
kPP8ZuYjI4+9Ng60zWRY2WtcnrlRUu0t3DZ0X+tGwPa2kBaUdsDhQxp34p1QH3DUzakTD2A1nAXU
XMHJoqQDp6GVqgF3EGBd08m3DCbfFp69G67cd/AF1bV5B62gv/bXB1RDb8eTdfAm0GNwg7vcgRFW
NsKCVGR8YRU9PfZXd9DqJ9SSrRTN46W6Vl+hkUbUTptrluFS8aOAHUJR9dwdqmGHjqw7OdlZRvuJ
xN9aqmImXgRoKsZa2QnGygfIo4G8zGQb1ZU2R1oUUwcl7BZBFAudaL988gnfalXRoogYbL4g2kl1
oivoef3O9wilg+8t8L4X3FgqEsIbgARLgHS65k5iGbgNm1frxHE09NumzERnRQiD+RQYq6Sywrji
5weYZefFxEXU2ERihM9jORVF5BiTSjo011/zsqyM4E1RZrd2JPGkbWutWrnPsmy7xexcfYC3k+wa
Ji4ORtPQaGFV7uBd6TMc8Adz3gvnk8NWsUlXBEMHasIztq4+W3ikVj5w01CVAyIkgggafRq62zsX
DcVU9Ua08kIxt+HvjrsWi0hFztHor7/kAbnW6ATVqtbHI1dNNaYwJDpuYEE0LuOGN1N33NpRqJhI
DL1CXyNaGkfeya+C6Z4qbKGwomsTIfoobtytEBrDzZUhOpYG/w+txNNs1mBFdAcvrxOx7JvySeNM
WoOww/J3LAD6AJvPWKtNWU7MTbKt5vmF9JbBrEO/Cnj8gw0E5A3Md5Oq7cZD35ijG1oNrWKfsoxC
J35koY39eBN6JFZ9wl9Gvp0ojWohlQ3FnO6mxWx9b+5g1UkCSxhuNg7LjOwWA5qg1u7zYGSbcJy4
oIAt5naHsLYxtqTsC9lYsC38RXSP81rzrgujJswj3i8GQkJACWVD22IMgdJx0npt5SUf+5V0fPYD
6W+QYSa5bAJPRWJbVVrVmUst2vjWwRPBMonai0tLR8VUaIwFOQSZCIkYubrDIAoP43J2SaYSqrFn
ibdGPos4L5cjHOphxFF/iILUy2x6RHeFaoqV8I1wJ6OCWPYfGhfRWTbzdEoir89GBRmbhUsdr4ga
DUXBanrkhyMezvQKomNme1Hjs6DeYfeF4uyI3QZsEMSwuWS9Yd87T9kpBWMZ7NTpzWWZ3QsS3xKN
rhkb5nf9MLuXfwrNTHeBJBLxPSTpuXYXSTxcImnxIdfgRUmnd5FNhYBI93+EehHVNKZ/AR4l7gOf
HK4DP0NypjsCPxx/cH9TTk0lZyvQJ6fFD9zsb5zqsRnsrXgZZCP+33qS0IfR0r28xmPT67jz13HU
I+qxSOoIeC2KGBQ9B2tX+lLnn59///T8Z+7/h0Aai0JTTorbLzeFV4zmFtcWb+V3fGsRH+KlEDVF
dzcCostZBOidYLnjGN2N6x/hZfD9OnFOVtNmjBrZ3bqt9NfKaXa3KxYdlnbMPy8itX8=
""".decode("base64").decode("zlib")

##file distutils.cfg
DISTUTILS_CFG = """
eJxNj00KwkAMhfc9xYNuxe4Ft57AjYiUtDO1wXSmNJnK3N5pdSEEAu8nH6lxHVlRhtDHMPATA4uH
xJ4EFmGbvfJiicSHFRzUSISMY6hq3GLCRLnIvSTnEefN0FIjw5tF0Hkk9Q5dRunBsVoyFi24aaLg
9FDOlL0FPGluf4QjcInLlxd6f6rqkgPu/5nHLg0cXCscXoozRrP51DRT3j9QNl99AP53T2Q=
""".decode("base64").decode("zlib")

##file activate_this.py
ACTIVATE_THIS = """
eJyNUk2L3DAMvftXiCxLEphmSvc2MIcu9NaWHnopwxCcRNlRN7GD7clM/n0lp5mPZQs1JLb8pKcn
WUmSPE9w9GReAM9Yt9RhFg7kSzmtoKE6ZGU0ynJ7AfIcJnuEE3Wd0nWgUQcEQWEkF466QzMCf+Ss
6dGEQqmfgtbaQIWcDxs4HdBElv7og1wBg3gmH0TMjykcrAEyAd3gkP8rMDaocMDbHBWZ9RBdVZIk
SgU3bRTwWjQrPNc4BPiue/zinHUz7DRxws/eowtkTUSyiMhKfi2y3NHMdXX0itcOpYMOh3Ww61g8
luJSDFP6tmH3ftyki2eeJ7mifrAugJ/8crReqUqztC0fC4kuGnKGxWf/snXlZb8kzXMmboW0GDod
Wut62G4hPZF5+pTO5XtiKYOuX/UL+ptcvy2ZTPKvIP1KFdeTiuuHxTXNFXYe/5+km0nmJ3r0KTxG
YSM6z23fbZ7276Tg9x5LdiuFjok7noks1sP2tWscpeRX6KaRnRuT3WnKlQQ51F3JlC2dmSvSRENd
j3wvetUDfLOjDDLPYtPwjDJb7yHYeNXyMPMLtdEQKRtl8HQrdLdX3O4YxZP7RvfcNH6ZCPMsi8td
qZvLAN7yFnoY0DSZhOUXj4WWy+tZ8190ud1tPu5Zzy2N+gOGaVfA
""".decode("base64").decode("zlib")

if __name__ == '__main__':
    main()

## TODO:
## Copy python.exe.manifest
## Monkeypatch distutils.sysconfig
