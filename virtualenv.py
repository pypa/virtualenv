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
        logger.info('File %s already exists', dest)
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
        # XXX: Jython's .bat sys.executable can't handle a command line
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
    if logger.stdout_level_matches(logger.INFO):
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
        version="1.1.1dev",
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
        for fn in os.listdir(stdlib_dir):
            if fn != 'site-packages' and os.path.splitext(fn)[0] in REQUIRED_MODULES:
                copyfile(join(stdlib_dir, fn), join(lib_dir, fn))
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
