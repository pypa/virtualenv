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

def install_setuptools(py_executable, unzip=False):
    setup_fn = 'setuptools-0.6c9-py%s.egg' % sys.version[:3]
    search_dirs = ['.', os.path.dirname(__file__), join(os.path.dirname(__file__), 'support-files')]
    if os.path.splitext(os.path.dirname(__file__))[0] != 'virtualenv':
        # Probably some boot script; just in case virtualenv is installed...
        try:
            import virtualenv
        except ImportError:
            pass
        else:
            search_dirs.append(os.path.join(os.path.dirname(virtualenv.__file__), 'support-files'))
    for dir in search_dirs:
        if os.path.exists(join(dir, setup_fn)):
            setup_fn = join(dir, setup_fn)
            break
    if is_jython and os._name == 'nt':
        # Jython's .bat sys.executable can't handle a command line
        # argument with newlines
        import tempfile
        fd, ez_setup = tempfile.mkstemp('.py')
        os.write(fd, EZ_SETUP_PY)
        os.close(fd)
        cmd = [py_executable, ez_setup]
    else:
        cmd = [py_executable, '-c', EZ_SETUP_PY]
    if unzip:
        cmd.append('--always-unzip')
    env = {}
    if logger.stdout_level_matches(logger.DEBUG):
        cmd.append('-v')
    if os.path.exists(setup_fn):
        logger.info('Using existing Setuptools egg: %s', setup_fn)
        cmd.append(setup_fn)
        if os.environ.get('PYTHONPATH'):
            env['PYTHONPATH'] = setup_fn + os.path.pathsep + os.environ['PYTHONPATH']
        else:
            env['PYTHONPATH'] = setup_fn
    else:
        logger.info('No Setuptools egg found; downloading')
        cmd.extend(['--always-copy', '-U', 'setuptools'])
    logger.start_progress('Installing setuptools...')
    logger.indent += 2
    cwd = None
    if not os.access(os.getcwd(), os.W_OK):
        cwd = '/tmp'
    try:
        call_subprocess(cmd, show_stdout=False,
                        filter_stdout=filter_ez_setup,
                        extra_env=env,
                        cwd=cwd)
    finally:
        logger.indent -= 2
        logger.end_progress()
        if is_jython and os._name == 'nt':
            os.remove(ez_setup)

def filter_ez_setup(line):
    if not line.strip():
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
        help="Unzip Setuptools when installing it")

    parser.add_option(
        '--relocatable',
        dest='relocatable',
        action='store_true',
        help='Make an EXISTING virtualenv environment relocatable.  '
        'This fixes up scripts and makes all .pth files relative')

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
                       unzip_setuptools=options.unzip_setuptools)
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
                       unzip_setuptools=False):
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
        pth = py_executable + '%s.%s' % (
                sys.version_info[0], sys.version_info[1])
        if os.path.exists(pth):
            os.unlink(pth)
        os.symlink('python', pth)

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
        if lines[0].strip() != shebang:
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
""".decode("base64").decode("zlib")

##file ez_setup.py
EZ_SETUP_PY = """
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
woheJi7S138BSGV4QQ==
""".decode("base64").decode("zlib")

##file activate.sh
ACTIVATE_SH = """
eJytU99P2zAQfvdfcaQ8ABqN+srUh6IhUYmViXSdNECum1waS6ld2U6zgva/75ykNP0xpGnkIYl9
n8/fffddB8aZtJDKHGFRWAczhMJiAqV0GQRWFyZGmEkVitjJlXAYwEVq9AJmwmYXrANrXUAslNIO
TKFAOkikwdjla8YS3JyCs3N4ZUCPTOERLhUEp/z+7gufDB/G3wd3/NtgfBvAM3wGl6GqkP7x2/1j
0DcE/lpq4yrg216hLDo4OFTFU8mqb6eu3Ga6yBNI0BHnqigQKoEXm32CMpNxBplYIQj6UCjWi4UP
u0y4Sq8mFakWizwn3ZyGOd1NMtBfqo1fLAUJ2xy1XYAfpK0uXBN2Us2bNDtALwScet4QZ0LN0UJJ
TRKJf63BC07XGrRLYo7JnrjXg4j0vNT16md0yyc3D9HwfnRE5Kq0S7Mjz9/aFPWOdSnqHTSJgAc9
inrvtqgJbyjUkE30ZjTZEjshXkSkD4HSKkHrTOGNhnvcOhBhnsIGcLJ3+9aem3t/M3J0HZTGYE6t
Vw5Wwkgxy9G2Db17MWMtnv2A89aS84A1CrSLYQf+JA1rbzeLFjrk/Ho44qPB1xvOrxpY2/psX0qf
zPeg0iuYkrNRiQXC007ep2BayUgc96XzvpIiJ2Nb9FaFAe0o8t5cxs2MayNJlAaOCJlzy6swLMuy
+4KOnLrqkptDq1NXCoOh8BlC9maZxxatKaU8SvBpOn2GuhbMLW5Pn71T1Hl9gFra8h77oJn/gHn/
z1n/9znfzDgp8gduuMqz
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
eJytVl2r4zYQfdevGBKKbcia0r5dCPvQD7jQlkILLZRF6NpyrK4jGUm+SfrrO2M5tmQnbR9qSJCl
o9HMmZljqXNvrAfjmAojd5uHF2G10icH94lvjG7U6WdhnbSwT1+VA208CHhX1g+ik/odzqYeOnkA
Z+AioRIaBidBefAGGqVr8K0E5+tOvTFWK6vFWcIRnSl74dtymqEl5wevOsdpPkL8aZTOV/A8dqvk
vFGd5Lw4QDabyQqmmtmINvZMgzw9poDjxpV8s2e2X7wwwOfOWUmDfJyiZ/crRhoxMx8Fvag+i5ME
4eELB6LvJTpOBL0hUzowRLR0phJeGQ3Chcmb8/K8GPq4K5jsnAxu8DEEzkulkQWff3mAVXQjTF5l
BaaXC4kjoykUmeNcaeXRXH/LiqK0UtR5we5lQfCofKqRf8bYfo/R+aqFt0F1NZdXD4tpqI10OvPw
WZsLtPjDmE/Sj8FhQSBAWVl5Y2+ToRYw+guWjbk4+EBl1ApbV6aWgRGCIIPWDFNljYfLmnwqeysb
dSWfm/DeCd9gEinJGRr9+qssMNdYE7FaVuZ8FroulxCmQJcJTIjB4Twxmqk64dwCyhPEVCv01LKh
VhCd+kty01OGHeROdk0Eoof8xtkSqbHC3jiy46jpfjJapkh6ttAj/PEpgbF/xEeFk5QGcYfp73gg
9AC7HzBXu6JIzCXRluv4QnhbZx5T/5Dw+YUHjQkG1rNR1o7L4liYyzE0mkrFvTBGrpM28VDGY3sT
ewQrv8U/q94GCqPcoNiUzHQ2TmYz1uYRHh4S0RKamy/NspK8TYNGrDWnLBjZRxonrwhw+dru5NZ+
9i1K+wY7J2wPv7ViFPFKdF1oNWk/DPQZCAEBBcSmskUfgrBjp/XGqWu21CvtGaOfpH+HCpPEsgs6
NQvbw00P96xRmzK+V3ACLCKvR7hytJSnoMUX1BBUIhRi1OoOnchHGre9S5hS6tpdFH41spXHWbFt
4ZAPK8/mXea0vWDpEn0rdJ0/cN9KP1gdYOw/FC6ysy3mtEtmXV+1Cio272++NRo/ERUamoFlujQ2
x7y42peTHHPXy0o1qjpi9YXkHEndJm6QxDC5Vb1pfjw8VqeYjK2z6aH3Iwv2zEm8S9Sm4nzq38eL
7Fn8MTWrvRsmUYifMUlXpadM4uKWSedRRPFDSatPmY1BQKL7P1K98Sr16V+IR8Rz4qPFx8SvmFzt
pRr//vX3H797gV9aM3Q1vE43ltTYtPmdbmYfqS/C80o3ELxx4N0Mb9BE4tA0B7z1uvH10iq0dL/m
OIkiEa512LF1yf4GZEHtwg==
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
