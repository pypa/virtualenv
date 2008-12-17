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
        version="1.3.3dev",
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
    # XXX: We'd use distutils.sysconfig.get_python_inc/lib but its
    # prefix arg is broken: http://bugs.python.org/issue3386
    if sys.platform == 'win32':
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
        # Jython has either jython.jar and javalib/ dir, or just
        # jython-complete.jar
        for name in 'jython.jar', 'javalib', 'jython-complete.jar':
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
        if (sys.platform == 'cygwin' and not os.path.exists(executable)
            and os.path.exists(executable + '.exe')):
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

    install_distutils(lib_dir, home_dir)

    install_setuptools(py_executable, unzip=unzip_setuptools)

    install_activate(home_dir, bin_dir)

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
eJx1kEEOgjAQRfc9xSxoAlfQkIiBCBFKg8iKZBbSKhu6kPvHFqQ0Ct3N9P2flzmJx0uBkpK8xQhN
VtX3KMeENSGiMyES0ksY1AidkP0gOuBVWfAafAL6mfC8CD3uXUgw4QuKZR7btr0c3aCoKTLMxl9I
F8Yp8VdrFhUJYgAW2zeK6tT10eOvjV7RCXiqUcHtmnGz0nb/clN6DpCDJddi56q0bRHPGfu6Hm0s
YTH5AJ7udMY=
""".decode("base64").decode("zlib")

##file deactivate.bat
DEACTIVATE_BAT = """
eJxzSE3OyFfIT0vj4spMU0hJTcvMS01RiPf3cYkP8wwKCXX0iQ8I8vcNCFHQ4FIAguLUEgWIgK0q
FlWqXJpcICVYpGzx2OAY4oFsPpCLbjpQCLvZILVcXFaufi5cACHzOrI=
""".decode("base64").decode("zlib")

##file distutils-init.py
DISTUTILS_INIT = """
eJytlcuq2zAQhvd6iuGEEhuC6ToQzqIXyKKl0C66EzrWOFarSEaSc3n7jizH8SWhXdSLoIx+jWa+
GY/VsbEugPVMpZW/DsuzcEaZg4eb4YM1lTp8E86jg9X0r/JgbAABJ+VCKzSaExytbDVuwFs4I5TC
QOsRVIBgoVJGQqgRfJBavTEmlTPiiLCjYIpGhLroLXHLhzYo7Xm0jxS/rDLZTJ6Nwyo4r5RGzvMN
rAc365ypanBirDvGRTa9JofdIpRscWbwn28Z0HNjVsRF1pni8/KDMh2RGa6CRpS/xQFBBHjnQTQN
UuAR0BuRMolQxKJtKYKyBoRPxqsPeLw7en3JGWqPKQzepcB5oQxRCNn7Dcyy62R4wRJsg3eIHdGp
lMhxrowK5K65rvO8cChklrNbW0T5qH3Kjj9jq9X9ziKuKNdQ1ui3jFkteewAnsQdRE+FjbLiI/04
9dbGdIuFikmsYGHNPOqqr0FlW+otKt6jS5Kw0yWE/F6LWWMtMNzTKavDOjlZjToJLySgG2Z++7BW
Q2yjqiy0ndRhaJ1JYvYPTCjyJadpAYbCzKpwwMCba6itoRqX5GgQFtOtjvuwOTuXNVoE7hssVaXK
HSXWOKzUZffVGuzzJ1DJGGdFtG+H16O3d5fH7tI8WcYwlsFOL71dmbNnQdIwkLbkvG+Nx5vsWf5j
NLOzC5I00J6RjLPuKUnaXJL0QRgpnIy7T8mORUDL/4l6EdU0pr+AJ8Vz8KPNx+BnJGdnY49/3v/8
8mkL32vbagn71N4z9v3hUxytr/G9SM8+QE3jVNBwpU9ghNhW1YY+W777e64VeZIWvVnTZEMat2ku
01dMFuwP2YOSYA==
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
