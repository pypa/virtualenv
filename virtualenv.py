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
                    'lib-dynload', 'config', 'zlib']

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
9DJxknz+C9YaISY=
""".decode("base64").decode("zlib")

##file activate.sh
ACTIVATE_SH = """
eJytU01P20AQve+vGBwOgJpYXKk4BDUSkWiocEqlErTZ2ON4JWc32l3HDaj/vbO2E5yPIlXFB9u7
8/XmzZsOjDNpIZU5wqKwDmYIhcUESukyCKwuTIwwkyoUsZMr4TCAi9ToBcyEzS5YB9a6gFgopR2Y
QoF0kEiDscvXjCW4iYKzc3hlQI9M4Qm6CoJTfn/3hT8OH8bf+3f8W398G8AzfAaXoao8/eOvr4+5
bj3w11IbVzlu7wpl0cFBUGVPJau+nbpzm+kiTyBBR5irpkCoBF5s9gnKTMYZZGKFIOhDplgvFt7s
MuEqvppUxFos8px4cxrmVJtooL9UG39YCiK2CbU9gB/ErS5cY3ZSzZs0O46eCDj1uCHOhJqjhZKG
JBL/WoMnnMoatEtCjskeuTf9iPjs6vr0M7rlj4OHaHg/OkJy1VrX7NDztzFFl8emFF0eDIkcD2YU
Xb47osa8gVC7bKyD0eMbsBPCRUCuIVBaJWidKbzQcA9bByLMU9g4nOxVf5Pnpu5vRoqujdIYzGn0
ysFKGClmOdq2oHcLM9b02IJ7HXDeOnIeMHagSeKt1nNzaAWEnN8MR3zU/zrg/Kpxa8ud7dPnk3ne
K46CKakZlVggTHbyToJpRR0B2qfLa0mKnMRs0csT+nSjSG9zGTd7rY0kIhp3RMicW16FYVmWvRd0
pM5VjxQcWp26UhgMhc8Qsq1MnlqwppTyKMDJdPoMdS+YW3yLPnunqfM6gMbY0hv7oD3/gB3/z/3+
993e7DUx8gesZMc6
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

if __name__ == '__main__':
    main()

## TODO:
## Copy python.exe.manifest
## Monkeypatch distutils.sysconfig
