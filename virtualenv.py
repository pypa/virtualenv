#!/usr/bin/env python
"""Create a "virtual" Python installation
"""

import sys
import os
import optparse
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
py_version = 'python%s.%s' % (sys.version_info[0], sys.version_info[1])
is_jython = sys.platform.startswith('java')
expected_exe = is_jython and 'jython' or 'python'

REQUIRED_MODULES = ['os', 'posix', 'posixpath', 'ntpath', 'genericpath',
                    'fnmatch', 'locale', 'encodings', 'codecs',
                    'stat', 'UserDict', 'readline', 'copy_reg', 'types',
                    're', 'sre', 'sre_parse', 'sre_constants', 'sre_compile',
                    'lib-dynload', 'config', 'zlib']

if sys.version_info[:2] == (2, 6):
    REQUIRED_MODULES.extend(['warnings', 'linecache', '_abcoll', 'abc'])
if sys.version_info[:2] <= (2, 3):
    REQUIRED_MODULES.extend(['sets', '__future__'])

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
        source = 'distribute-0.6.7.tar.gz'
        project_name = 'distribute'
        bootstrap_script = DISTRIBUTE_SETUP_PY

    search_dirs = ['.', os.path.dirname(__file__), join(os.path.dirname(__file__), 'virtualenv_support')]
    if os.path.splitext(os.path.dirname(__file__))[0] != 'virtualenv':
        # Probably some boot script; just in case virtualenv is installed...
        try:
            import virtualenv
        except ImportError:
            pass
        else:
            search_dirs.append(os.path.join(os.path.dirname(virtualenv.__file__), 'virtualenv_support'))

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

def install_setuptools(py_executable, unzip=False):
    _install_req(py_executable, unzip)

def install_distribute(py_executable, unzip=False):
    _install_req(py_executable, unzip, distribute=True)

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
        version="1.3.4dev",
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
        help="Use Distribute instead of Setuptools")

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

    if os.environ.get('PYTHONHOME'):
        if sys.platform == 'win32':
            name = '%PYTHONHOME%'
        else:
            name = '$PYTHONHOME'
        logger.warn('%s is set; this can cause problems creating environments' % name)

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

    py_executable = install_python(
        home_dir, lib_dir, inc_dir, bin_dir,
        site_packages=site_packages, clear=clear)

    install_distutils(lib_dir, home_dir)

    if use_distribute:
        install_distribute(py_executable, unzip=unzip_setuptools)
    else:
        install_setuptools(py_executable, unzip=unzip_setuptools)

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
    else:
        lib_dir = join(home_dir, 'lib', py_version)
        inc_dir = join(home_dir, 'include', py_version)
        bin_dir = join(home_dir, 'bin')
    return home_dir, lib_dir, inc_dir, bin_dir

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
    for stdlib_dir in stdlib_dirs:
        if not os.path.isdir(stdlib_dir):
            continue
        if hasattr(os, 'symlink'):
            logger.info('Symlinking Python bootstrap modules')
        else:
            logger.info('Copying Python bootstrap modules')
        logger.indent += 2
        try:
            for fn in os.listdir(stdlib_dir):
                if fn != 'site-packages' and os.path.splitext(fn)[0] in REQUIRED_MODULES:
                    copyfile(join(stdlib_dir, fn), join(lib_dir, fn))
        finally:
            logger.indent -= 2
    mkdir(join(lib_dir, 'site-packages'))
    writefile(join(lib_dir, 'site.py'), SITE_PY)
    writefile(join(lib_dir, 'orig-prefix.txt'), prefix)
    site_packages_filename = join(lib_dir, 'no-global-site-packages.txt')
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
        if py_executable.endswith('/Python'):
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
                    prefix, 'Resources/Python.app/Contents/MacOS/Python'),
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

def install_distutils(lib_dir, home_dir):
    distutils_path = os.path.join(lib_dir, 'distutils')
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

def fixup_pth_and_egg_link(home_dir):
    """Makes .pth and .egg-link files use relative paths"""
    home_dir = os.path.normcase(os.path.abspath(home_dir))
    for path in sys.path:
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
ptryW2MQ/B+3QrZo
""".decode("base64").decode("zlib")

##file ez_setup.py
EZ_SETUP_PY = """
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
178BYnMUkw==
""".decode("base64").decode("zlib")

##file distribute_setup.py
DISTRIBUTE_SETUP_PY = """
eJztG2tz28bxO3/FlRoPwJiEJCdNW02ZGceWU01d2yPJyQdZAx2Bo4gIr+AAUcyv7+7eA4cHJTtJ
O9OZ0jMWiNvb29ft644Hfyp39abIJ9Pp9PuiqGVd8ZLFCfxNVk0tWJLLmqcprxMAmpyt2a5o2Jbn
NasL1kjBpKibsi6KVAIsjlas5NEdvxWeVINBuZuznxtZA0CUNrFg9SaRk3WSInr4Akh4JmDVSkR1
Ue3YNqk3LKnnjOcx43FME3BBhK2LkhVrtZLBf3IymTD4rKsic6gPaZwlWVlUNVIbttQSfPeVPxtw
WIlfGiCLcSZLESXrJGL3opIgDKShnTrHZ4CKi22eFjyeZElVFdWcFRVJieeMp7Wocg4yNUAtx3Na
NAKouGCyYKsdk01Zprskv50g07wsq6KsEpxelKgMksfNTZ+Dm5tgMrlEcZF8I1oYMQpWNfAskZWo
SkpiT2uXqCxvKx67+gzQKCZaeIU0T3JnH+skE+Z5nWe8jjZ2SGQlUmC/84q+Wg01dYImo0bT4nYy
qavdSatFmaD1qeGPF6fn4cXZ5elEPEQCSD+j96coYjXFQrAle1fkwsFmyG5WIMJISKlMJRZrFirj
D6Ms9r/i1a2cqSn4wa+AzAd2A/Egoqbmq1TMZ+w5DVm4CuRV5Q76IAKJ+oSNLZfsaLKX6AMwdBA+
qAa0GLM1aEERxF4EX/+hRB6wX5qiBmPC100m8hpEv4blc7DFFgxeIaYStjsQkyH5HsB8/cJrlzRk
IUKBbM66YxqPB/9gc8P4cNgRmzd9Jqcee4aAAzgN0x/STF+1FJDo4EGvKK/72ilkIEsOu86Hpw/h
Ty/PLuesJzT2lauz16dvXn58exn+eHp+cfb+Haw3PQq+Db6d2pGP52/x7aauy5PDw3JXJoHSVFBU
t4faB8pDCX4qEofxYeuWDqeTi9PLjx8u379/exF++OcP4dm7N+8R2XT6afIvUfOY13zxo3I0J+w4
OJq8Aw954mzOiR0FsqK/TS6aLONg8uwBPpN/FJlYlLA+fZ+8bICuyn1eiIwnqXrzNolELjXoa6G8
A6HGF+gDJhMyRO0tfNjLK/g7M1YsHiBqRGRe5KDVMA3WWQlODlgz/iDI7mJ8Bl+L47Dxgy2vct87
bZGAFp9Jb64nK8AijcNtDIhAgbeijraxxmD3OUHB7tvAHN+dSlCciFBOKChKkVsuLEyo+dAsdiYH
UVpIgQGi3VK3hSYWmbau3AKAR1CsA1ElrzfBzwCvCZvjyxQMwqH16uh6NmREYWkHWoG9K7ZsW1R3
rsQMtEOlVhoGkiGOMzvIXlvz9NrVuJQCfKfrgjwTc2E5TyPXM9ZJDl/G1KG0NzOGtGoSeCFub40S
QNdFiJT/36T+B0yK1EfBJGegxBFE31sIx64QtlWE0ncrqX0mtvgF/1+h90SLoVcL/Ab/VQ4ihz7l
9I3tVEI2aW2HMVSY1NOVmGt/5gNxTKc1gf7r41QgoXXmi2fyqwAJgyDWCxojkbGNR47+aOk5UeXw
UfEEEsez95Qw+N6rokljlhe1Ej+xBssGX7r3YlhN55++TmXnNiMNV1wKI1PndSxSvtPsaCMHK7TD
TgK6B+VoDtD97FmUZqLlLB/zGwRFuQuKFdwSuC3/aI4TZ50ssJv/O8nuylQ/JsyFlIYuycKV7Hq5
tmZ12dN6j/Wlky+MikFxsER9NdWIBJbHf56D3sM1vxPLN5DMC+slM05bVTZQoWwpiySz4CtZpLjh
UBiTdg3HcQAI/vVd8W25DJWYBHpFr7y7DWHzUP4iKZtDAWdF3KRCYsnwybLjtWLpAw49aueLo5vO
ev19iIa/4ZLXdeV3AGEzhrETu0azUZytRTiejuJItxLsQ+jt2ObwFmJfem9nqj3/e3beftl1ZBHo
ctWfthL5bjl9rlebjZDV56KLTyeZr4p8nSZR3V1agJGoHDqCPbMu/NnV8XVfb65RDUWP08H/iqoK
thUUfP4AYnpJLpzYit3a2+lR+N8tn0HiDjUv6pnfQ2ZLGf2nfDrEhy0FqIq9GusuvdUB83aDMYH6
DLo8hieomDGMBOxDKkA9o/hMCc1ZVlRIKiTTtSV0nVSynsPOBDSj0z1AvDMuhy0+Onx5wQj8p/xT
7r9qqgpWSXcKMXtWzQA5BKDWrkSA1QwmAENTVkpLav9Fd0yAbxnqCCyQ9Xacs72vem7iGqdgCKYG
R3G3LwJ+yW74jODB9u6YUbu2SQms+q6o3xRNHv/uTfskmWMkDuJ2GFWC1yLseaQQGaBdZhMeDEmP
hODfG5foMxKcdEzSjhbKw9dtO8tuSYqdtmkG+ystIuohUktPCzepVZcqh9pW5T03mvYbJjeU76yw
9XbP06SD3eyuvMlWooJdy2m72p1PuLDVRfkppXy25waapimC3XTkccOwoPfBD0Qbs7rIYxUZsR/J
mXfozQJ2o2Rygyt20nTwIaISJjGzvR2ziogDxSNJ0E7XPFA3MSrymPp6JcdYvhJrdCnYwovqhqdt
d5H4q7HoqQOjhv9ITtCJN6TUpoJ6cUWRRmBLV/dWqxQroImz40bjoYPixdjc+vbXEM0BmyGdHDvA
iun2V3RyWvuqgVt1ElFUJHtusagcj98LEGm/aNKB1oDqDLKKEB3wpduI+FLnD2Y6eE5ZS1+hnZ2g
zF/eFwladYk7N7bktEnMIGzbUsnuHvLjcjpHlrpuWRGlpeQPhg/YueDxIcVPhkEEC5scrAe23N0c
u8lbNEKMeMq1gCVHRVWBu6Dd10MG3JJVm/2SYF+/FgRvTNh8sE2FSUAVgT3wuJc1KTES0UpYczbd
rqYDIB36EVk7NvCLWhOw1kgaAQSYaroHD/hHQhos6sL3qjLgJaWdoHVsSqcSK8AQZebj8BzECJLJ
69YV/kR7nkd3TUlSXKukQuSM5oLHMxuVrAh0HmocRlKIeOZKE3gYwi7N0i1vB6B7nLZTS4l4pCx/
2YUInE6PFgHVF702ygeExjQoMBMgkuKeCUlIRLGKZS4TkJdvvTEnotVtZDceBddj+rmsGmF0gSdG
Rh6j2jA67QvVEZ7BNeBGYcjF1vgifAt+xQvev30dPJNY6+PZR4D/DdpO54hObWfcOoVqeCgaDc59
3tUpSCVEylXxYLzkaxNmLtR7O49YuE8KdUY3OCLAT8ll64v6iIJ2MtbY9suTvpywqk4aVh7Ilj/G
pdaEedlKPSvuIc+B1UL3lNEvUx6JTZFCnNZ89DxwIrGvMQTrquFjfgc+rHOACTFTK8OZu38LrDEt
BJm4b0abR+Ok7O8etVqm1tEC87p+5WoWJ6N3B1Zgx3euWNbd7LWVQNsyouzLPdtz1+0JYDIwZ9AT
mrNIhTo5Kpoa8xV0cFu+a92CSVH7sdYRj+lyafJ7GtXzZ66NkadCw1TeF8gOO7DKTDuVy2CSctl6
xpyNHL7ovpuWqEYwJlPY07zvReesS82oMR0A5i1LRe1JhoZv40NfntbQtLzR1ny3wTLvtWZ0oxQP
TPHRkZ7B8Jg+NMzMNdteqmNAugbacZsDLMNacswuwe+rTiaI1RCrJeGN1yTeRXvfIHaqOK/HyUjI
4GtIY+whFk7WHDkBEkHsqbhtCVoDbwWHaSJgwIMDCENZBr40LFY/++2RSGD6iCWk4pDvqsj5VHXX
8UyK7i+Z0vGXLrlgTyNJ7FM+dERTRjimoBv6D5LU7p5kBPtFx0s6o9apO9F9dXStOgmdl8f6xMJh
lBzu0vWaCzrzXJQ7wG79GKxBq36+K+qtMfBKRkhDtzTqDxT4I96gZ2yvUK8qTxhMalMp67UeT6dG
fRoBPJ5alfXGCHi/oBzRBzDB62c8PU40yj4n+vVTnHTIcBoPfW09yV4na7dxo83vDrQ3Bice3aHe
E/w2lkXvtSaV557+8MMCBY5eGISvnr/AmpJBPvtoqNrnVj83NDnusQ1Pe1J6ID67s3LrvnpUFLMn
UoInJfdf2wEjkUI1XmyoGISJ71VjZm+cGJ4maMTUfArLSqyTB9940NZp2+BBLlefo0A+f9/S7lKL
3/VlGAN4ZR4g+sTiwQlHz49Prm1qQYNzc2VG5E0mKq4u07i1A4Kq22YqCVksKmBVHcEqJvpZKzAB
OAJYs6olts3QLJfomxWekeOZuih1I4pmlmlS+x6us/RmV4veiYIjAiM+dzGNq9/WVlRh5aeoGD0j
SsHW1A2g75R8xk+KOuTKK4J8PkLlb6ZUCxzvXi0WjRSVRz3T9oabPufA/tTeA+axJS2GfXY/MNu+
3V9EnA5EnHMTc89pbGfuPdd7rKo8YFvhweaKgISReOukf2CczuWCuBBKLlKIDHuo7vHOsNNBX7e4
dbq5tL7+gGIYMuSEIEz+YPJWBpgZdY8kg3N1XoXZKPi8ClxNJ38fz2x7aqQAjBj0me/MldzlrhQD
uUGwdpvkLz+c/cGEz9oqqY8QbLJrj+6lEveOsJuzq8p1XDUHLBa10Jd3MDTjSaKNb2ipcT9PtEcM
yz55gRnq27N7d9lpE6ilwbpNv2BkFS0Lapgqv4gGSX4xeSBiywrq5ljE6hpzstbw7oVp6VTnsb73
k83bhq3pGrpZfTeIjFE2rgWNDQQ67xMMiFSfd+w22NBa1c1OoGUDOf7+OqCTZMGuVHqU7q0hzdII
E4HIYx1A6HbNHqbyhbpU1CqvQwfu7/2NplGtmsmaNMAxdjA40nVw7p3tJ2lfPjRCyuPpkSbR35dd
os11y/UvyDD3ppiPNJB7sunOG7aQXduwxxK4rensTLk/Osdy/H0u+qrt5va/V589eukkJxdO0zvl
TR5t2nSufdOPlOd6pMMzhja24dj7wV8WKAgqqs3NdIQy15u715Ov2XOb5CnHZw7xR2+eWxKdC4hS
pGvVh15Og+mcZQJPHuUSHXd7hKEvTdJJkoZQrWk6RayAJUU/fo3UPQRzZ9DItT0RRceHP4wotjnW
kVkR408olJPF3jkBlKLKEinpNw1F3keSgKapcwOCjWXAbpABz54s4+8ZAOlaECGDK5NAqJYAPMJk
zZGH7k4lWjwlIjL8fQqdNoM8iWRqQxk82OnVpgJmsdqxW1FrXP6sewSrs56oKHfud6hlIMXW14aU
QNXVUQOgBd/eLXIlAPZwbYOvUcsg6JoBDIDpemLTfViJnA64bQ3SKT71sO7C9jb/gSGsQ48+EZd8
LVCroncu2EIGvIQiLvb1Gl1/YehakrQC/O9RQLx0gp2Kb775KyUIUZKB+qhKAfqO/nJ05GQ86TrQ
qjc4lfHbwH0usPMkmETpuyTbJKfXnGJ/Z/6LOfvGkRDuMZwvKh8wHM8Rz4vZmIdhUVYSTIB1tgIM
2kOSvtgQqa8wjwNUinp/rAE+QHQndktjgAHeoQPzRZo9JMCbzZnGtsRqwAoI0iM6KQZcdgfbXYum
S+rAfKkvvJ7ROeMdIulYbbQzYBTeFdDgGJ20HG2AuFbHGu9sCNjQcd1nAEYb4OwRQJ2Fuzv2N1yN
UyaKk1OQfgpl5/FIPYfXDntF4tgtLUIWxqtbH4xwql3LCd4ogNpbmHCQ8YSK3Ps523NLqA0EZ4/9
NoxM4JTLnYYyzu/xy8E6kPZ/RwLEYQuMTgfDkCrfMERSw1D/8Ijotj2O45Pr2eTf6Tlt5A==
""".decode("base64").decode("zlib")

##file activate.sh
ACTIVATE_SH = """
eJytU11P2zAUffevuKQ8AFqJ+srUh6IhgcTKRFgnjSLXTW4aS6ld2U6zgvbfd50PSD+GNI08JLHv
8fW5557bg4dMWkhljrAsrIM5QmExgVK6DAKrCxMjzKUKRezkWjgM4Cw1eglzYbMz1oONLiAWSmkH
plAgHSTSYOzyDWMJtqfg5BReGNAjU3iEvoLgmN/dfuGTm/uH76Nb/m30cB3AE3wGl6GqkP7x28ND
0FcE/lpp4yrg616hLDrYO1TFU8mqb6+u3Ga6yBNI0BHnqigQKoFnm32CMpNxBplYIwj6UCjWy6UP
u0y4Sq8mFakWizwn3ZyGBd1NMtBfqo1frAQJ2xy15wA/SFtduCbspFo0abaAXgg49rwhzoRaoIWS
miQS/9qAF5yuNWhXxByTHXEvRxHp2df16md0zSdX99HN3fiAyFVpfbMlz9/aFA0OdSka7DWJgHs9
igbvtqgJtxRqSBu9Gk/eiB0RLyIyhEBplaB1pvBGwx1uPYgwT6EFHO3c3veh1qHt1b8ZmbqOS2Mw
p+4rB2thpJjnaLue3r6bsQ7VYcB5Z8l5wBoRuvWwPYuSjLW9m0UHHXJ+eTPm49HXK84vGljX/WxX
TZ/Mt6GSLJiRuVGJJcJ0K+80mFVKEsdd9by1pMjJ2xa9W2FEO4rst5BxM+baSBKlgSNC5tzqIgzL
sjx/RkdmXZ+ToUOrU1cKg6HwGUL26prHDq0ZpTxIcDqbPUFdC+YW306fvFPUaX2AWtqxH/ugsf+A
kf/Pcf/3UW/HnBT5Axjqy2Y=
""".decode("base64").decode("zlib")

##file activate.bat
ACTIVATE_BAT = """
eJx9kMsOgjAQRfdN+g+zoAn8goZEDESJPBpEViSzkFbZ0IX8f+RRaVW0u5mee3PanbjeFSgpKXmI
Hqq4KC9BglFW+YjWhEgJJa2ETvXQCNl2ogFe5CkvwaUEhjPm543vcOdAiacjLxzzJFw6f2bZCsZ0
2YitXPtswawi1zwgC9II0QPD/RELyuOb1jB/Sg0rNhM31Ss4n2I+7ibLb8epQGco2Rja1Fs/zeoa
cR9nWnprJaMspOQJdBR1/g==
""".decode("base64").decode("zlib")

##file deactivate.bat
DEACTIVATE_BAT = """
eJxzSE3OyFfIT0vj4spMU0hJTcvMS01RiPf3cYkP8wwKCXX0iQ8I8vcNCFHQ4FIAguLUEgWIgK0q
FlWqXJpcICVYpGzx2OAY4oFsPpCLbjpQCLvZILVcXFaufi5cACHzOrI=
""".decode("base64").decode("zlib")

##file distutils-init.py
DISTUTILS_INIT = """
eJytVl2L6zYQffevGBKK7XavKe3bhVBo78uFSyml0IdlEVpbTtR1JCMpm6S/vjOSY0v+uO1DDbs4
0tF8nJk5sjz32jjQNpPhzd7H1ys3SqqjhcfCL1q18vgbN1YY2Kc/pQWlHXB4l8ZdeCfUO5x1c+nE
E1gNVwE1V3CxAqQDp6GVqgF3EmBd08nXLGukUfws4IDBVD13p2pYoS3rLk52ltF6hPhLS1XM4EUc
VsVYKzvBWPkE+WgmLzPZjkaUNmd6KVI3JRwWoRSLM6P98mMG+Dw4q+il8Ev07P7ATCNmRlfQ8/qN
HwVwB99Y4H0vMHAi6BWZUoEhoqXTNXdSK+A2LN6tE+fJ0E+7MhOdFSEM5lNgrJIKWXDF908wy87D
xE3UoHsxkegZTaHIHGNSSYfm+ntelpURvCnK7NEWBI/ap/b8Z1m232N2rj7B60V2DRM3B5NpaLSw
KnfwpvQVTviHOR+F88lhQyBAGlE7be6DoRNg9ldsG3218IHa6MRNU+tGBEYIggwafRk6yzsXDcVU
9Ua08kYxt+F3x12LRaQi52j0xx/ywFxrdMRqVevzmaummlIYEp0WsCAaX8cFb6buuLUTqEgQQ6/Q
04iWRoF38m/BdE8VtlBY0bURiB6KG1crpMZwc2fIjqWh+1UrkSLpWUIP8PySwLKv4qPGSVqDuMPy
dywQ+gS7L1irXVkm5pJsq3l+Ib1lMOvUrxI+/mBBY4KB+WpUtcO06RtzckNvQ6vYj1lGoZM2sdDG
fryJPYJVn/Cfka8XSqNaoLKhmOlqXMzW9+YBVp1EtIThZtOwzCRvMaARa+0xD0b2kcaJGwJsMbc7
hLUfY4vKvsCOBdvDnyfuRbzmXRdGTZgPF7oGQkJACWVD22IMQdhx0npt5S2f+pXO+OwH6d+hwiS5
7IJOjcK2emj1zBy1aONHByfAMoraw6WlrSIFTbGghqASoRCjVncYROFpXM4uYSqhGnuVeGvks4jz
cjnCoR5GnPW7KOh4maVbdFeoplgJ3wh3MSrAsv/QuMjOspnTKRl1fTYqqNisv7uTVnhF1GhoBFbp
lh+OcXN2riA5ZrYXtWxlfcDuC8U5kLoN3CCJYXGpesO6dx6rU0zGMtjU6cNlmW0Fid8Sja4ZG+Z3
fTPbyj+mZnZ2wSQK8RaT9Km0ySRuLpm0DkUUL0ra3WQ2BgGJ7v9I9SKqNKZ/IR4R28RHm+vEz5ic
nZ2IH7bfub8pU1PR3gr10W7xLTfHh6Z6bgZ7K14G7Mj/1z5J6MFo6V5e07H0Ou78dTyeI+mxKOpI
eC2KMSj6HKxd6Uudf/n886fPv+f++x1lbASlmjQuPz8OvGA0j7j2eCu/4bcW6SFeCuNJ0W1GQHI5
iwC9Ey0bjtHd9P4dPA++XxLnZDVuxvFEtlm3lf5a2c02u2LRYXHH/AOs8pIa
""".decode("base64").decode("zlib")

##file distutils.cfg
DISTUTILS_CFG = """
eJxNj00KwkAMhfc9xYNuxe4Ft57AjYiUtDO1wXSmNJnK3N5pdSEEAu8nH6lxHVlRhtDHMPATA4uH
xJ4EFmGbvfJiicSHFRzUSISMY6hq3GLCRLnIvSTnEefN0FIjw5tF0Hkk9Q5dRunBsVoyFi24aaLg
9FDOlL0FPGluf4QjcInLlxd6f6rqkgPu/5nHLg0cXCscXoozRrP51DRT3j9QNl99AP53T2Q=
""".decode("base64").decode("zlib")

##file activate_this.py
ACTIVATE_THIS = """
eJx1UsGOnDAMvecrIlYriDRlKvU20h5aaY+teuilGo1QALO4CwlKAjP8fe1QGGalRoLEefbzs+Mk
Sb7NcvRo3iTcoGqwgyy06As+HWSNVciKaBTFywYoJWc7yit2ndBVwEkHkIzKCV0YdQdmkvShs6YH
E3IhfjFaaSNLoHxQy2sLJrL0ow98JQmEG/rAYn7OobVGogngBgf0P0hjgwgt7HOUaI5DdBVJkggR
3HwSktaqWcCtgiHIH7qHV+esW2CnkRJ+9R5cQGsikkWEV/J7leVGs9TV4TvcO5QOOrTHYI+xeCjY
JR/m9GPDHv2oSZunUokS2A/WBelnvx6tF6LUJO2FjjlH5zU6Q+Kz/9m69LxvSZVSwiOlGnT1rt/A
77j+WDQZ8x9k2mFJetOle88+lc8sJJ/AeerI+fTlQigTfVqJUiXoKaaC3AqmI+KOnivjMLbvBVFU
1JDruuadNGcPmkgiBTnQXUGUDd6IK9JEQ9yPdM96xZP8bieeMRqTuqbxIbbey2DjVUNzRs1rosFS
TsLAdS/0fBGNdTGKhuqD7mUmsFlgGjN2eSj1tM3GnjfXwwCmzjhMbR4rLZXXk+Z/6Hp7Pn2+kJ49
jfgLHgI4Jg==
""".decode("base64").decode("zlib")

if __name__ == '__main__':
    main()

## TODO:
## Copy python.exe.manifest
## Monkeypatch distutils.sysconfig
