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
    
join = os.path.join
py_version = 'python%s.%s' % (sys.version_info[0], sys.version_info[1])

REQUIRED_MODULES = ['os', 'posix', 'posixpath', 'ntpath', 'fnmatch',
                    'locale', 'encodings', 'codecs',
                    'stat', 'UserDict', 'readline', 'copy_reg', 'types',
                    're', 'sre', 'sre_parse', 'sre_constants', 'sre_compile',
                    'lib-dynload', 'config']

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
        logger.warn('Cannot find file %s', src)
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

def install_setuptools(py_executable):
    setup_fn = 'setuptools-0.6c7-py%s.egg' % sys.version[:3]
    setup_fn = join(os.path.dirname(__file__), 'support-files', setup_fn)
    cmd = [py_executable, '-c', EZ_SETUP_PY]
    env = {}
    if logger.stdout_level_matches(logger.INFO):
        cmd.append('-v')
    if os.path.exists(setup_fn):
        logger.info('Using existing Setuptools egg: %s', setup_fn)
        cmd.append(setup_fn)
        env['PYTHONPATH'] = setup_fn
    else:
        logger.info('No Setuptools egg found; downloading')
        cmd.extend(['--always-copy', '-U', 'setuptools'])
    logger.start_progress('Installing setuptools...')
    logger.indent += 2
    try:
        call_subprocess(cmd, show_stdout=False,
                        filter_stdout=filter_ez_setup,
                        extra_env=env)
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
        help="Don't copy the contents of the global site-packages dir to the "
             "non-root site-packages")

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

    create_environment(home_dir, site_packages=not options.no_site_packages, clear=options.clear)
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
    if stdout is not None:
        stdout = proc.stdout
        while 1:
            line = stdout.readline()
            if not line:
                break
            line = line.rstrip()
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
            raise OSError(
                "Command %s failed with error code %s"
                % (cmd_desc, proc.returncode))
        else:
            logger.warn(
                "Command %s had error code %s"
                % (cmd_desc, proc.returncode))


def create_environment(home_dir, site_packages=True, clear=False):
    """
    Creates a new environment in ``home_dir``.

    If ``site_packages`` is true (the default) then the global
    ``site-packages/`` directory will be on the path.

    If ``clear`` is true (default False) then the environment will
    first be cleared.
    """
    if sys.platform == 'win32':
        lib_dir = join(home_dir, 'Lib')
    else:
        lib_dir = join(home_dir, 'lib', py_version)
    inc_dir = join(home_dir, 'include', py_version)
    if sys.platform == 'win32':
        bin_dir = join(home_dir, 'Scripts')
    else:
        bin_dir = join(home_dir, 'bin')

    if sys.executable.startswith(bin_dir):
        print 'Please use the *system* python to run this script'
        return
        
    if clear:
        rmtree(lib_dir)
        rmtree(inc_dir)
        ## FIXME: why not delete it?
        logger.notify('Not deleting %s', bin_dir)

    prefix = sys.prefix
    mkdir(lib_dir)
    fix_lib64(lib_dir)
    stdlib_dir = os.path.dirname(os.__file__)
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

    if sys.exec_prefix != sys.prefix:
        if sys.platform == 'win32':
            exec_dir = join(sys.exec_prefix, 'lib')
        else:
            exec_dir = join(sys.exec_prefix, 'lib', py_version)
        for fn in os.listdir(exec_dir):
            copyfile(join(exec_dir, fn), join(lib_dir, fn))

    mkdir(bin_dir)
    py_executable = join(bin_dir, os.path.basename(sys.executable))
    if 'Python.framework' in sys.prefix:
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
    
    if 'Python.framework' in sys.prefix:
        logger.debug('MacOSX Python framework detected')

        # Create a dummy framework tree
        frmdir = os.path.join(home_dir, 'lib', 'Python.framework', 'Versions', 
            '%s.%s'%(sys.version_info[0], sys.version_info[1]))
        mkdir(frmdir)
        copyfile(
            os.path.join(sys.prefix, 'Python'),
            os.path.join(frmdir, 'Python'))

        # And then change the install_name of the cpied python executable
        try:
            call_subprocess(
                ["install_name_tool", "-change",
                 os.path.join(sys.prefix, 'Python'),
                 '@executable_path/../lib/Python.framework/Versions/%s.%s/Python' %
                 (sys.version_info[0], sys.version_info[1]),
                 py_executable])
        except:
            logger.fatal(
                "Could not call install_name_tool -- you must have Apple's development tools installed")
            raise

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

    install_setuptools(py_executable)

    install_activate(home_dir, bin_dir)

    install_distutils(lib_dir)

def install_activate(home_dir, bin_dir):
    if sys.platform == 'win32':
        files = {'activate.bat': ACTIVATE_BAT,
                 'deactivate.bat': DEACTIVATE_BAT}
    else:
        files = {'activate': ACTIVATE_SH}
    for name, content in files.items():
        content = content.replace('__VIRTUAL_ENV__', os.path.abspath(home_dir))
        content = content.replace('__VIRTUAL_NAME__', os.path.basename(os.path.abspath(home_dir)))
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

def create_bootstrap_script(extra_text):
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
    """
    filename = __file__
    if filename.endswith('.pyc'):
        filename = filename[:-1]
    f = open(filename, 'rb')
    content = f.read()
    f.close()
    return content.replace('##EXT' 'END##', extra_text)

##EXTEND##

##file site.py
SITE_PY = """
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
""".decode("base64").decode("zlib")

##file ez_setup.py
EZ_SETUP_PY = """
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
""".decode("base64").decode("zlib")

##file activate.sh
ACTIVATE_SH = """
eJx9VEFu2zAQvPMVE7mHJGgs+JrCBxct0AJBW9RuekgCmZZWFgGJNEjKqlv0713KsqXYaXQQRO4s
OTuzqxEWhXLIVUmoauexItSOMjTKF4icqW1KWCkdy9SrrfQU4Tq3psJKuuJajLAzNVKptfGwtYby
yJSl1Jc7ITI6ZOHyCn8E+FE5HnCjEb1Jvt59SO4/f1/8mN0l32aLTxGe8A6+IN0iwxO2py9Bjwj6
tTHWt8DjXq0deZwltfFcvUpjPnmJxXxyRoKBZxzmk1cpdGFmIHrIIfrxy31P7IJ5MZEpIm10Rs7b
OghJJ9xGmFOZ4wC4OLm9l/9w71/Bju2Dyloq5Za0x1ZaJVcluaFhzy8WoqtxQHcaJclgmSSREGea
s257v7rFICHmtrrtokMXxalq4YwgdyvNkhuPtKwIw7OWmE6RJKfyuA2lSpbcoI6QG4sZ72hUcq3S
rk+NVVx4BydC4f3mNo6bphn/Ji8z2o5TU8XO5L6RlmIZTojFsS0eekKPSz7yjNrjcvmEfQFUOuoz
L/9TytUezHYN+op9ayfVFaYuM7bWM/d2CN+iKVRaoJAOMrwLMOFK6oyVkL4da87mwU5lWfJoe4N1
aAAfvliUsNhInv0uzY2Bnzz+pg55e4BXev0cFGRG6x7SQuo1OTT8D2HB+LXj9ukutRRM8JSJfuTe
z+anw97yvrGh6n+DYGAl
""".decode("base64").decode("zlib")

##file activate.bat
ACTIVATE_BAT = """
eJx1kE0LgkAQhu/zK+bggv6FQkhQSvJjMfMkDJS75cU95P+n3SwbUPc2s8/78jAHdX8aNFrDS43Y
pFV9jTJKiiYkYhMRQK9xMCN2SveD6lBWZS5r9AHtc+FpEXrSO0LwwX8olVk8t23lhFjBhHBVjlr5
tJGZYkX+37yI8oQoQAZue0X1iVvZceFkd7bCIQ8zGrycU+l21nGpOOW/EdjNLCtnBxaibW/9sGeJ
pIjhDfhHdDA=
""".decode("base64").decode("zlib")

##file deactivate.bat
DEACTIVATE_BAT = """
eJxzSE3OyFfIT0vj4spMU0hJTcvMS01RiPf3cYkP8wwKCXX0iQ8I8vcNCFHQ4FIAguLUEgWIgK2q
KhZlqqpcmlwgRVjkbHHbEe4f5O3p5x4f4BjigWwTkItkT2gIyCygGA5bQKq5uKxc/Vy4AOHQPcY=
""".decode("base64").decode("zlib")

##file distutils-init.py
DISTUTILS_INIT = """
eJyNkMtuxCAMRfd8haUuEqQR6rpSd/0PRIOZcUVMBM48/r4kmck80kVZIGQf7rUv9UPKAqkoWl4n
l5l4X+Dt/qQCnAQcHCnL6CLyEfrkx4g7KAlOCJ1jGAsCCUiCQOxBDghFfKRvpTxldj3CZzUyg5OD
uVamVpFRKBY71R+In0TcvuDtbSRjbaCI1uodNKtEo5WdZaw1xAWztO87eHbQCs/YQRrwrj5bPWNV
1lpikio1XBqtTUbnW61uOU24Uil6O21ru8SB9vNQpS4xdc1XvTJ9V9HEZkMpjwE21bZgDPpDQT0h
jTXHmshfJgs4c+VSBHu7LvAa4maztWC6sG8WEQrrJzzXfjV4kb1OtU72EPEGncmMMmZeYPWPROrc
25TUL6lF7+4=
""".decode("base64").decode("zlib")

##file distutils.cfg
DISTUTILS_CFG = """
eJxNj00KwkAMhfc9xYNuxe4Ft57AjYiUtDO1wXSmNJnK3N5pdSEEAu8nH6lxHVlRhtDHMPATA4uH
xJ4EFmGbvfJiicSHFRzUSISMY6hq3GLCRLnIvSTnEefN0FIjw5tF0Hkk9Q5dRunBsVoyFi24aaLg
9FDOlL0FPGluf4QjcInLlxd6f6rqkgPu/5nHLg0cXCscXoozRrP51DRT3j9QNl99AP53T2Q=
""".decode("base64").decode("zlib")

if __name__ == '__main__':
    main()

