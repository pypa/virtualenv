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
        version="1.3.3",
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
        import win32api
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
eP8HyeK9cQ==
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
eJytVsuq3DAM3fsrxAwlCUxD1xeGu+gD7qKl0EK7M76JMnGbsYPtzOPvK9uZPGdoF80iONKRLB1J
duSx1caBtkzGlb0Oy7MwSqqDhZvgvVaVPHwVxqKB7fxTWlDagYCTNK4TDaoTHHXZNbgDq+GMUAgF
nUWQDpyGSqoSXI1gXdnIV8ZKaZQ4IuwpmLwVrs57iVdZ1znZWO7lE8QvLVW6gKfTsHLOK9kg59kO
ksFNkjFZDU6UNke/SOfbZLBfhZKubAb/2RMDem6c5X6RBpF/Nt8p0wkzw1bQiuK3OCAIB28siLZF
CtwT9EpMqciQp6XRhXBSKxA2Cq/W4XF09LzJGDYWYxg8pMB5LhWx4NJ3O1hkF2B4wQJ0iyOJgdE5
lJjjXCrpyF17TbIsNyjKNGO3tvDwSfsUgX/Gtttxz9yvKFdX1GifGNNNyX0H8AgOJFoqrIflH+hl
5Gvn081XKFZiBStparGp+hpUuqPeouLd2yQCAy5SyMdaLBprRcOYTlEdkuhkO+kkvBCAdlj47cPa
DrFNqrLCDi2zhR+1CKNSiKYJNW/RvO38sMWEwCcU8DGGOD57SFpt5SV5Glx5m5B9P2AbquMsl03s
hqF97hrdtVmiZgRScnlrsJKX3RyYTaIOcGm9Kp2DxlgqTQeMb3eaiIaCSAONE0DvzmNyVKU9S5rN
ZBFxsjAY62HwqE+YevOMzVV+IlWZ3gnfoOuMijD2D41L7KybeT4lw/QsRuWAjrdXV2tFg1iQowGY
z1VhOAblwi5tG+G4bbGQlSz21H2xOPsvWt3YJhKj0B/oXj5S1svD5v4IaHiUTMlYBzvf9LZlxh4F
SSd2qQvO+/m9r2SP8p9Ss7BdMUm3ziMm/YX0kElSrpm0TqhSmNJrHzI7BQEt/yfVq6jmMf2FeEI8
Jn6ivE/8gsmFre/xTy8/P398gm+17poSXmJ7L7jvjU/+/nv2cxGfFwc13XmCbkD6T/EkdlW1o38L
Gz7PtSRPpUarErp+kA6JeHnSxJY5+wM7qxSa
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
