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
        version="1.3dev",
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
            os.execvpe(interpreter, [interpreter, __file__] + sys.argv[1:], env)

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
        for name in 'jython.jar', 'javalib':
            copyfile(join(prefix, name), join(home_dir, name))
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
                  'activate', 'activate.bat', 'active_this.py']

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
            if lines[0].strip() == new_shebang:
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
A2n5eOU=
""".decode("base64").decode("zlib")

##file ez_setup.py
EZ_SETUP_PY = """
eJzNWmtv20YW/a5fwagwJCEyzfdDgbLoNikQoOgWaVNg4XjleVpsKJIlKTvaRf/73jvDp2Qp7SIf
lkVqmxzeuc9zzx3pmxfFod7m2WQ6nf49z+uqLklhVKLeF3Wep5WRZFVN0pTUCSyavJPGId8bTySr
jTo39pUYr8WnpVEQ9ok8iFmlH5rFYWn8tq9qWMDSPRdGvU2qiUxSga/UWxBCdsLgSSlYnZcH4ymp
t0ZSLw2ScYNwrl7ADXFtnRdGLvVOrfzVajIx4JJlvjPEvzfqvpHsirysUctNr6VaN741X5xYVorf
96COQYyqECyRCTMeRVmBE3Dv/tUl/g6reP6UpTnhk11Slnm5NPJSeYdkBklrUWakFt2i3tKl2pTB
Kp4bVW7Qg1HtiyI9JNnDBI0lRVHmRZng63mBQVB+uL8/tuD+3pxMfkE3Kb8ytTFKFEa5h98rNIWV
SaHMa6KqtCweSsKHcTQxGSaN86pDNXnz9vtvP/zwy+bXt+9/fvePH421MbXMgMXT7smH9z+gW/HJ
tq6L1c1NcSgSU+eWmZcPN01OVDdX1Q381212MzWucBOzce/tyr2bTHbc33BSExD4HxWwWf/GNexN
7evi4JiuKR4eZitjFkWOw4iMLdvxLR55EY3jgIbS8VkgAkZmywtSvFYKDWMSEc9yhedbjqQ08oVw
pR17duj6jJ6R4ox18QM/DP2YRyTgkWSeZ4UWibkVOqHD4/iylE4XDwwgEbeDmDtUBIEtieuQQPiO
8GTknLPIHetCqWszS7LQjWMSuH4Yx6HPCI+lT6zAji5K6XRxIxIxuMsDwbjjOF4o7TCWISdBEEvC
zkjxxroEjuX5xPEE94QtKAtDKSw3JsQTgQyFf1FK7xdGHWJHPugRccKkpA63QR/LpS61mfe8FHaU
L9SVDvV9N+YBxDWUoUd4GNsOCCKxFZ2xiB3nC9jDBQdPBiF3uCOlsD3Lit3Akw7xzkSaHeWLtKzA
ozIgxKEht6RLiUU9UNCK7JA54UUpnS6BHdixIwRzfemFIhLEDhgPiO2AVCc8J+UoX6QdQaJBEXEp
IgiWH7MYpEibhzSM5JmsY0f5IizBQy+IHBbHEZU0dKmMLJf4lgAxtrgoxW+lECqkHUjOwTDf920v
8mwWQh7yOIoD/5yUo6yjFo1t1yaMUNexwBmQr6H0POZDwENbXpTSWQQpJ2HPgHuSSpfFIZWxFzAL
XAXZK5yLUjqLIqw6KGDXYZzGLHQokx6koRNIJyLyXNb5Y4uEiCWPLFAHMg8STboCatMPAwGYYwfn
Iu2PLSJSOIRLQAc7tGwhwLkhgIxPGQAXCc7VkX8Uo4i7MrC92GOMkCi0PUgc7oaUMe5yn5+REowt
cv0gArSObDsARIkiL3RABCCf78WCOdZFKT1KMT8g0g8p+Be6AFRDYIEhnudCgfnkXDUGY4uoIyMS
+g6Adkx86gLYWhBqLnwJLcF3z0gJxxY5FsRIxoQzlwS2L3zb9qEMoTVEwnbP5ks4tsgnkYx9L7JC
7gXEkjQImbSlA2GAR865CgjHFnmAlYQ7ICrEAvRcz7ZtyUXk2vAvPKdLdNTVLOxpTgweiTmNGKZg
SEnkWtggrctSOosYJW4E2AC9w4tcZmHOQraBsxkT4OSLUjqL7NCxQwA5CHTMme1bfmwRP6KugDqP
/XORjscWge7Ms6Ap2ehh6sWB8JikworAVmadi3R8hAyQZNCgHeG7UcQDQCcihBUAeLHA9c716UZK
Z5EUEFpX+MQOqe0wCBPzPZuGgnguiUQAUv6YDCgZ8MtqUpeHlWa8W1Jt04S2hBfY00R8ZgK43jt1
5y1y0mYtPByum3Ahjc0jSRPgW2IDt+ag0yYDQr40kIItVsqARBrtfSTtLUHTD/HiCbC7GggbilAv
mlvxWd8Fgt0uAznNyhfrTsptK/qul4cXEF+g469fIz+sai5KINbz0Qq8pmhSY0FD0K+ABhPgwfyF
Ycx/yqsqoemAfwOnhr93f1tMT4RddWaOHi1Gf6E+4nNSzx19v4Tglplyl3boETtXixqCuz5i08tO
rQ0llVgPKPUSqPoGZoV1XplsX8JvOpm6F7hIyWFt+5MmSMDbv93X+Q78wIDeH2AWyPhNZ/ZgVMPB
akc+QSxhenkEVxF0EDgPTStIvdXz1H2j9L1RbfN9ynGcINrXQ2ntaJTtd1SUMKURmPWqXrCShSNI
ht41JIwdnVL7jKtXhHE/csS9gUPF/GmbsG27uwCtcTbU8ozZzWxhgpLaS/e4JcoZzJFbUY4m1KcE
hh7aZ4LgS8hIneBK5SwHf6SlIPzQqw97wHh4P3a72q4ZDpWYutFSSaNCqdI4RI2MLM94pX3TqlEQ
SBR0KngEyyqpYdCD0W8wUOqIN/bnmVADnR5OudYLnJqn6MNnB1TUspn2RCNMDdNlvoedhFZF1xkx
dqKqYEjTE2ZfdPf3Kl9KksBE+/OhqsXu7Wf0V6YDAeNlDff0aEkoQgsajymIxuix02wzVP18ItVG
oxDYvzZmxaeHTSkqmOmZqGaIMLj9Luf7VFQ4pg4A9PixrgmoOg550LhtvuiRBFNu3RfNoC4bjx2V
YFt2y6NC6zGgLRITPCvKem4tcZMByDVA3e30ajhe0/acZdMEZqOAeY0ydIAA2I9ljRykHj6D8N1L
LSANHdI8Ot1hJNpskms+7TV+vZ6+bFy1eNXIHqowFvCrXvldnsk0YTW4ZjVE/2Hk/yraT3/Z9tl/
Jt/nr9dX1aKr5baG1VnSx2wM+FNGslmNJdWVCGAGnp+oGmnOS7Ba9lkGqWwaP6UCMqRdfiIPawhL
GQBIgC2thjIpK3DEvsJymIGEQxt64/rDQPmZeSTvY/Yxm3+3L0uQBnCuBVyVR31rAV2rz2VhkvKh
urXuLvcsFb+0EuMYQKKPw7kcVtrtUZ3e4SvfgLUKyfNPI1HP5eD5rHmTQEkkdI8d/Me8/j6HvnA5
n3Wnfa6sv3a7xeKH8hz12TfPNFVVxqRvCkaaM01JFHxqG5JaH9EpivF/2mQ1ROMhbNtkv9Rj8R7u
etpgNe7f9z3zTF/MdTdsmyE2FVbvSdob0TSZcSNpz3hL6DXUgWzdQgqlOs9avro2BmB2fVUB976q
kHpPh4VzdAipcxXkDnsH+sx4OaaIFXkUoP0aKLluCr/lSTZvW0i7VIurSobiFE/+Ebp5S60RqtrX
oUirupprsYsVFti3j3mCCVQIgv2yVafq6mOE53ipVOQgCL1RtV5K84fRKiTjGJfxu3jBSvOJlNkc
/Xz99S59RN0Aa4Pk1XNZfqVSAo+u5+JRZPgHmFOAspOtSAvkfe90tg24R5cqQE4w//FwfY6umEBL
WBqALhO8tYNyzgQ4El6BOkTmCwgtnhCPCQyiVaXeHvYAheDmpNkSoLvhOP2OoDJvs9mcTOYAYmKF
HlZidoRtkW7xXOjGtIXwghL1U15+ajZdGoXuLjmtSfPBCCKFQomrajJBFAEPMMXa1QKQ3FdiUzml
aLrV0ABz8TWjCEmxPEmZAeieECqVZUusppPXgFGoZK0TnCwb4pQKUbzSP+ZH3GucnS0Mq75YTdUW
R31PlVyDDyb8zAuRzU+WfWO8B9J/81QmNYAPxBj8q+g2YPinJX4284TRQ7rASixDgEaWl+VeJUcq
joSpuA/TA1l4LdT6FhPbq/mg49wQDgaYOJDMF2ONNYooazRWLKdPdAruhAemskOP4d1LMAziULg6
hgDYYKV2YWleifniBCKqeqWEDp833awFLVAwxV9a2Jr8mQv79w4yfQ6E5XF5rmP3PffdpU+tVI99
C9SqWdU2iOfI9NGngZeYtB4eOqw+kdivuTxgqEndOqVk4zFiNEWomGFpDGYHlu92YKg54pDtcQ5p
BrL2amKkXJxCL1B+XrzE05a7hUrTJzErVVoLA9v4F1MFLUU/H/UqVPu0h8CifQYT4Kd5Z9aYcCZD
4m5uNo23NhtjDSOhZVqmPfvLI8I/AeAVuOJcTKs8FVCrZ0bjlvRDM9HE/oTQl2KXPyq8VZHQHzqr
CRg6Rw3Qm34Bd4+Y+llK3hTV72OyMpi8hmzndBj8EwMd/LzAv4+mttX5bP+fU/JSmXWCvyjlJJuf
q7u23O7GM7tytrWAxAersPtD4JjKFHzyfIbiLl/JAZ36SvMLU5hO8+nPJ7RoumwRZQog+KAaUYnH
v5CEQJL6hJ4+I282fw90atp+PcIsDuPpc6q/+HD63QBzMWuONYuuP7UjTNXD8wf11MASofskra/1
OTGIfMDh7oCIPMzispl/kGu158qd2N4hinP37Br/xBXznlUrIW0vVE1zVtJZ/6w7ZsZ375ojatk2
1WePqWXX7PQIqFv07RT/uCpX8G8JWAHjQ8M0NSFrNzKh+e6q+eKue9mswOKudRY4VEynelLQTXro
GIgAjJB1OzGoL3Ss27vmg6h10eL9+XA63yjGsNk0Wd+5pJGxNJRbXjWUqHXAq2Njd6SGaXANepqV
ICXbzqcfs+E3Mj5m89t//XH3cvHHVNGTxXCMUW8PsOgZxIZGrr4SkxoCUeDF9LRIW0TUqsL/b1dK
sKmo99xe3MEYphz5Uj3VD2F0hUeru+fNnz01OSEbetSpPnDABMxo/bhezzYbLNjNZtZ9CpKiRFBT
1fBrR7XD9u9b+w7eub4GZ+lSGbSvQe10y53V3XN9UWFELxMX6eu/qpVkow==
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
