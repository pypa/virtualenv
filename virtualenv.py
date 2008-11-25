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
    setup_fn = join(os.path.dirname(__file__), 'support-files', setup_fn)
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
        version="1.3.1",
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
    distutils_cfg = DISTUTILS_CFG + "\n[install]\nprefix=%s\n" % home_dir
    writefile(os.path.join(distutils_path, '__init__.py'), DISTUTILS_INIT)
    writefile(os.path.join(distutils_path, 'distutils.cfg'), distutils_cfg, overwrite=False)

def fix_lib64(lib_dir):
    """
    Some platforms (particularly Gentoo on x64) put things in lib64/pythonX.Y
    instead of lib/pythonX.Y.  If this is such a platform we'll just create a
    symlink so lib64 points to lib
    """
    if [(i,j) for (i,j) in distutils.sysconfig.get_config_vars().items() 
        if isinstance(j, basestring) and 'lib64' in j]:
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
fmsMvP8Dbwf1Bw==
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
eJytlUmr2zAQgO/6FcMLJTYE03MgvEMXyKGl0B56E3rWOFbrSEaSs/z7jizHa0x7qA9BnhnN8s1k
rM61sR6MYyqe3L0/XoXVSp8cPAQfjC7U6ZuwDi1spq/KgTYeBFyU9Y2oUF/gbGRT4Q6cgStCLjQ0
DkF58AYKpSX4EsF5Wak3xqSyWpwRDpRMVgtfZp0kqJxvvKocD/KRxS+jdDIzT8ZpZZwXqkLO0x1s
ezfblKmid6KNPYdDMg2TwmGRSrK40/tP9wzoeTDLwiFpReF5+UGVjsj0oaAW+W9xQhAe3jkQdY2U
eAD0RqR0JBSwVCYXXhkNwkXh3Xk8D45eX1KGlcOYBm9L4DxTmij45P0OZtW1ZnjDHEyNA8SW6NSU
yHGutPLkrr5v0zSzKGSSssdYBPPR+OQtf8Y2myFmFk5Uq89LdHvGTCV5mAAejVuIjhobzLKP9GPV
WxPKzRZWTGIBC2nisCq6HhSmodmi5j0LEg1bu4iQD72YDdYCw1BOXpy20clokPBGegowc9tl1Wc2
6snCtLW06BurozH7ByKU95LSFH/fllkPTuh5ffel0dThnBz1htlU1VLvlbN7SV0Jz12NuSpUfqDC
aouFuh2+Go1d+cQpCsOmCPKBSidvg4fZqniUjGEsk50GfYRM2VqStAqkyTnvBuO5kq3VP0Yzu7sg
SetsjWTYdKskSbkk6bzQUlgZtKtkx0ZAx/+JepHVNKe/gCeLdfAj5XPwM5Kzu2HGPx9/fvm0h++l
aSoJxzjeM/bd5UtYrK/hfxGfo4eSlqmg1UofwACxKYodfbRc+3otFXmSBp3e0l5DWrZxK9M3TGbs
D3BIkho=
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
