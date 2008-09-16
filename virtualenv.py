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
                    'lib-dynload', 'config', 'zlib', '__future__']

if sys.version_info[:2] == (2, 6):
    REQUIRED_MODULES.extend(['warnings', 'linecache', '_abcoll', 'abc'])
if sys.version_info[:2] <= (2, 3):
    REQUIRED_MODULES.append('sets')

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
    setup_fn = 'setuptools-0.6c8-py%s.egg' % sys.version[:3]
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
        version="1.2dev",
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
        shutil.copyfile(sys.executable, py_executable)
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

    install_distutils(lib_dir)

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

def install_distutils(lib_dir):
    distutils_path = os.path.join(lib_dir, 'distutils')
    mkdir(distutils_path)
    writefile(os.path.join(distutils_path, '__init__.py'), DISTUTILS_INIT)
    writefile(os.path.join(distutils_path, 'distutils.cfg'), DISTUTILS_CFG, overwrite=False)

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
PsjP+MofdihQ3fE9L3qtjixwaTTIYBL8P2RhDrE=
""".decode("base64").decode("zlib")

##file ez_setup.py
EZ_SETUP_PY = """
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
9DJxknz+C9YaISY=
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
