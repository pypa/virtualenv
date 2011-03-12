#!/usr/bin/env python
"""Create a "virtual" Python installation
"""

virtualenv_version = "1.5.2"

import sys
import os
import optparse
import re
import shutil
import logging
import tempfile
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
py_version = 'python%s.%s' % (sys.version_info[0], sys.version_info[1])

is_jython = sys.platform.startswith('java')
is_pypy = hasattr(sys, 'pypy_version_info')

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

if sys.version_info[:2] >= (2, 6):
    REQUIRED_MODULES.extend(['warnings', 'linecache', '_abcoll', 'abc'])
if sys.version_info[:2] >= (2, 7):
    REQUIRED_MODULES.extend(['_weakrefset'])
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
        source = 'distribute-0.6.14.tar.gz'
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
                       use_distribute=options.use_distribute,
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
        inc_dir = join(home_dir, 'include')
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

##file site.py
SITE_PY = """
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
""".decode("base64").decode("zlib")

##file ez_setup.py
EZ_SETUP_PY = """
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
qL7+C1AkCcw=
""".decode("base64").decode("zlib")

##file distribute_setup.py
DISTRIBUTE_SETUP_PY = """
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
""".decode("base64").decode("zlib")

##file activate.sh
ACTIVATE_SH = """
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
""".decode("base64").decode("zlib")

##file activate.fish
ACTIVATE_FISH = """
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
""".decode("base64").decode("zlib")

##file activate.csh
ACTIVATE_CSH = """
eJx9U11vmzAUffevOCVRu+UB9pws29Kl0iq1aVWllaZlcgxciiViItsQdb9+xiQp+dh4QOB7Pu49
XHqY59IgkwVhVRmLmFAZSrGRNkdgykonhFiqSCRW1sJSmJg8wCDT5QrucRCyHn6WFRKhVGmhKwVp
kUpNiS3emup3TY6XIn7DVNQyJUwlrgthJD6n/iCNv72uhCzCpFx9CRkThRQGKe08cWXJ9db/yh/u
pvzl9mn+PLnjj5P5D1yM8QmXlzBkSdXwZ0H/BBc0mEo5FE5qI2jKhclHOOvy9HD/OO/6YO1mX9vx
sY0H/tPIV0dtqel0V7iZvWyNg8XFcBA0ToEqVeqOdNUEQFvN41SumAv32VtJrakQNSmLWmgp4oJM
yDoBHgoydtoEAs47r5wHHnUal5vbJ8oOI+9wI86vb2d8Nrm/4Xy4RZ8R85E4uTZPB5EZPnTaaAGu
E59J8BE2J8XgrkbLeXMlVoQxznEYFYY8uFFdxsKQRx90Giwx9vSueHP1YNaUSFG4vTaErNSYuBOF
lXiVyXa9Sy3JdClEyK1dD6Nos9mEf8iKlOpmqSNTZnYjNEWiUYn2pKNB3ttcLJ3HmYYXy6Un76f7
r8rRsC1TpTJj7f19m5sUf/V3Ir+x/yjtLu8KjLX/CmN/AcVGUUo=
""".decode("base64").decode("zlib")

##file activate.bat
ACTIVATE_BAT = """
eJyFUkEKgzAQvAfyhz0YaL9QEWpRqlSjWGspFPZQTevFHOr/adQaU1GaUzI7Mzu7ZF89XhKkEJS8
qxaKMMsvboQ+LxxE44VICSW1gEa2UFaibqoS0iyJ0xw2lIA6nX5AHCu1jpRsv5KRjknkac9VLVug
sX9mtzxIeJDE/mg4OGp47qoLo3NHX2jsMB3AiDht5hryAUOEifoTdCXbSh7V0My2NMq/Xbh5MEjU
ZT63gpgNT9lKOJ/CtHsvT99re3pX303kydn4HeyOeAg5cjf2EW1D6HOPkg9NGKhu
""".decode("base64").decode("zlib")

##file deactivate.bat
DEACTIVATE_BAT = """
eJxzSE3OyFfIT0vj4spMU0hJTcvMS01RiPf3cYkP8wwKCXX0iQ8I8vcNCFHQ4FIAguLUEgWIgK0q
FlWqXJpcICVYpGzx2BAZ4uHv5+Hv6wq1BWINXBTdKriEKkI1DhW2QAfhttcxxANiFZCBbglQSJUL
i2dASrm4rFz9XLgAwJNbyQ==
""".decode("base64").decode("zlib")

##file distutils-init.py
DISTUTILS_INIT = """
eJytV92L4zYQf9dfMU0ottuse/TeFkKh3MvC0Ydy0IdlMVpbTtR1JCMpm+T++s5Y/pBs53oPZ1hQ
pPnSb34zo5WnVhsH2jLpV/Y2Li/cKKkOFoYN3Za6ErAdFtKC0g44vEvjzrwR6h1Oujo3YgdWw0VA
yRWcLUo6cBpqqSpwRwHWVY18ZRB9W3jq3HDlfoIvqK7NG2gF7a297VANvZ3O1sGrQI/eDe5yB0ZY
WQkLUpHxhVX09NDe3FGr31BL1lJUD9f8ln+FShpROm1ujOFS8ZOAPUKRt9wd836Hjqw7O9nYgvYD
iX+1VOlMPPXQ5EVRy0YURbaDZDSQZEzWo7rS5kSLNHaQwX4RRLrQGe1nj92Fh1zltEhHDDZfEO0g
O6MraHn5xg8IpYOfLfC2FdxYShLC64EES4A0uuROYhq49Zs368RpMvTHJmOiscKHUXRXKIpcKiuM
Sz/sYHa7TkxcRYkkEhN8HZaxKCJXFFJJh+baW5JluRG8SjM20JHEA9qWWtXywBjbbvF2rjzC61k2
VSGuDibTUGlhVeLgTekLHPEP73wQrrscUsUGrPCGjkTCC1JXXyw8EJWP3FSUZY8IiSCCRp97dnfO
RUUx5a0RtbxSzLX/3XBXYxIpyQka/fh74pGrjQ5QzUt9OnFV5dMV+otOG5gQjctxozNTNtzaSSiN
JHqu0FeJmsqRN/KrKHRLGbaQWtHUgRB9FDfu5giN4eZWIDqWCv8vrcTjrNZgRXQPzy+RmGjQpLRI
EKz0UqQLlR28ciusM8jn7PtcLPZy2zbSDeyyos0iO+ybBgPyRvSk/CEFm8IndQebz8iXTRbbjhDP
5xh7iJfBrKd/Nenjj6Jvgp2B+W7AnP102BXH5IZWPV3tI2MUOvXowpdS12IIXhLLP0lKyeuZrpEv
pFhPqHg3JFTd1cceVp0EsPgGU0wFO2u4iyYRoFYfEm9kG/RZcUUBm87t9mFtx9iCtC9kx4Rt4R8a
OdgzSt40vtyFecAZZ8BfCOhCrC8djMGPFaz2Vlt5TSZCk053+37wbLDLRXfZ+F45NtdVpVWdudSC
xgODI8EsiLoTl5aO0lhoigX7GHZDHAY4LxoMIu1gXPYPksmFquxF4uRKZhEnKzXu82HESb+LlNQz
Fh/RvFJVuhK+Ee5slBdj30FcRGdJ5rhKxtkyKxWcGoV/WOCYKqkNDYJ5fNQVx3g400tpJBS2FSU+
Tco9ss8nZ08dtscGQfSby87b73fOw+4UgrEMNnY6uMzYvSDxPVPpsij6+l0/ZPfuH0Iz010giY34
HpL0ZLyLJB4ukaQRU+GwptO7yIZCQE33B0K9iCqO6X+AR4n7wAeH68DPkJzpTsD3x+/cj9LIVHC2
An1wmv7CzWHoqR02vb0VL73siP+3nkX0YbQ0l9f6WDyOm24cj3rxO2MMip6kpcu6VCefn/789PR3
0v0fg21sFIp70rj9PCi8YDRDXFucym/43qN+iENh1Jy/dIIIqF3OIkDvBMsdx+huWv8Kz73vl8g5
WQ3JOGqwu3lb4dfKKbvLigXDQsb8B/xt39Q=
""".decode("base64").decode("zlib")

##file distutils.cfg
DISTUTILS_CFG = """
eJxNj00KwkAMhfc9xYNuxe4Ft57AjYiUtDO1wXSmNJnK3N5pdSEEAu8nH6lxHVlRhtDHMPATA4uH
xJ4EFmGbvfJiicSHFRzUSISMY6hq3GLCRLnIvSTnEefN0FIjw5tF0Hkk9Q5dRunBsVoyFi24aaLg
9FDOlL0FPGluf4QjcInLlxd6f6rqkgPu/5nHLg0cXCscXoozRrP51DRT3j9QNl99AP53T2Q=
""".decode("base64").decode("zlib")

##file activate_this.py
ACTIVATE_THIS = """
eJyNUlGL2zAMfvevEBlHEujSsXsL9GGDvW1jD3sZpQQ3Ua7aJXawnbT595Ocpe0dO5ghseVP+vRJ
VpIkn2cYPZknwAvWLXWYhRP5Sk4baKgOWRWNqtpdgTyH2Y5wpq5Tug406YAgKEzkwqg7NBPwR86a
Hk0olPopaK0NHJHzYQPnE5rI0o8+yBUwiBfyQcT8mMPJGiAT0A0O+b8BY4MKJ7zPcSSzHaKrSpJE
qeDmUgGvVbPCS41DgO+6xy/OWbfAThMn/OQ9ukDWRCSLiKzk1yrLjWapq6NnvHUoHXQ4bYPdrsVX
4lQMc/q6ZW975nmSK+oH6wL42a9H65U6aha342Mh0UVDzrD87C1bH73s16R5zsStkBZDp0NrXQ+7
HaRnMo8f06UBnljKoOtn/YT+LtdvSyaT/BtIv9KR60nF9f3qmuYKO4//T9ItJMsjPfgUHqKwCZ3n
xu/Lx8M/UvCLTxW7VULHxB1PRRbrYfvWNY5S8it008jOjcleaMqVBDnUXcWULV2YK9JEQ92OfC96
1Tv4ZicZZZ7GpuEpZbbeQ7DxquVx5hdqoyFSSmXwfC90f1Dc7hjFs/tK99I0fpkI8zSLy4tSy+sI
3vMWehjQNJmE5VePlZbL61nzX3S93ZcfDqznnkb9AZ3GWJU=
""".decode("base64").decode("zlib")

if __name__ == '__main__':
    main()

## TODO:
## Copy python.exe.manifest
## Monkeypatch distutils.sysconfig
