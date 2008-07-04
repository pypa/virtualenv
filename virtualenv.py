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

def copyfile(src, dest):
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
    if hasattr(os, 'symlink'):
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
    if os.name == 'posix':
        oldmode = os.stat(fn).st_mode & 07777
        newmode = (oldmode | 0555) & 07777
        os.chmod(fn, newmode)
        logger.info('Changed mode of %s to %s', fn, oct(newmode))

def install_setuptools(py_executable, unzip=False):
    setup_fn = 'setuptools-0.6c8-py%s.egg' % sys.version[:3]
    setup_fn = join(os.path.dirname(__file__), 'support-files', setup_fn)
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
    ## TODO: this should all come from distutils
    ## like distutils.sysconfig.get_python_inc()
    if sys.platform == 'win32':
        lib_dir = join(home_dir, 'Lib')
        inc_dir = join(home_dir, 'Include')
        bin_dir = join(home_dir, 'Scripts')
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
        else:
            exec_dir = join(sys.exec_prefix, 'lib', py_version)
        for fn in os.listdir(exec_dir):
            copyfile(join(exec_dir, fn), join(lib_dir, fn))

    mkdir(bin_dir)
    py_executable = join(bin_dir, os.path.basename(sys.executable))
    if 'Python.framework' in prefix:
        if py_executable.endswith('/Python'):
            # The name of the python executable is not quite what
            # we want, rename it.
            py_executable = os.path.join(
                    os.path.dirname(py_executable), 'python')

    logger.notify('New python executable in %s', py_executable)
    if sys.executable != py_executable:
        ## FIXME: could I just hard link?
        shutil.copyfile(sys.executable, py_executable)
        make_exe(py_executable)
    if os.path.splitext(os.path.basename(py_executable))[0] != 'python':
        secondary_exe = os.path.join(os.path.dirname(py_executable), 'python')
        py_executable_ext = os.path.splitext(py_executable)[1]
        if py_executable_ext == '.exe':
            # python2.4 gives an extension of '.4' :P
            secondary_exe += py_executable_ext
        if os.path.exists(secondary_exe):
            logger.warn('Not overwriting existing python script %s (you must use %s)'
                        % (secondary_exe, py_executable))
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
    if sys.platform == 'win32':
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
HgWiNQ==
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
eJx1kMsKgzAQRff5ilkY0F9oESoordRHUOtKmIUmrRtTav6fJooaWs1uJudeDnPh7UuCFIKMXEEd
F9UjSDDKah/RmhAJ6QUMUkHHRT/wDliRp6wCl4B+JjwvfIc5V+JN+IJinoRr21GO7lDUFBlm58+n
C2OVuJt1FqQRogcrdmwUVDfbR4+/NnpFJ+AplYTyHjOz0nb/clN6DpDTSm7F1lVp05Ttp3+r8bwm
oiwkX126c9k=
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
