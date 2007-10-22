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


def create_environment(home_dir, site_packages=True, clear=False):
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
        bin_dir = join(home_dir, 'Scripts')
    else:
        lib_dir = join(home_dir, 'lib', py_version)
        bin_dir = join(home_dir, 'bin')

    if sys.executable.startswith(bin_dir):
        print 'Please use the *system* python to run this script'
        return
        
    if clear:
        rmtree(lib_dir)
        rmtree(inc_dir)
        ## FIXME: why not delete it?
        logger.notify('Not deleting %s', bin_dir)

    if hasattr(sys, 'real_prefix'):
        logger.notify('Using real prefix %r' % sys.real_prefix)
        prefix = sys.real_prefix
    else:
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
    
    if 'Python.framework' in prefix:
        logger.debug('MacOSX Python framework detected')

        # Create a dummy framework tree
        frmdir = os.path.join(home_dir, 'lib', 'Python.framework', 'Versions', 
            '%s.%s'%(sys.version_info[0], sys.version_info[1]))
        mkdir(frmdir)
        copyfile(
            os.path.join(prefix, 'Python'),
            os.path.join(frmdir, 'Python'))

        # And then change the install_name of the cpied python executable
        try:
            call_subprocess(
                ["install_name_tool", "-change",
                 os.path.join(prefix, 'Python'),
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
s257v7rFICHmtrrtokMXxalq4YwgdytNtOTOIy0rwvCwZasWczhVyG0oVbLkHnWE3FjMeEejkmuV
dq1qrOLaOzgRCu83t3HcNM34N3mZ0Xacmip2JveNtBTLcEIsjp3x0FN6XPKRZ+Qel8sn7Gug0lGf
efmfYq72YHZs0FpsXTusrjB1mbG7nrm3c/gWTaHSAoV0kOFdgAlXUmeshPTtZHM2z3Yqy5Kn2xus
Qw/48MWihMVG8vh3aW4M/OQ/gKlD3h7glV4/BwWZ0RqItJB6TQ4N/0ZYMH7tuIO6Sy0FEzxlop+6
97P56by3vG9sqPofb6xgcA==
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
FlWqXJpcICVYpGxx2xDuH+Tt6eceH+AY4oFsD5CLsCU0BGQUUAi7HSC1XFxWrn4uXAAdwT0y
""".decode("base64").decode("zlib")

##file distutils-init.py
DISTUTILS_INIT = """
eJytlD3P2yAQx3c+xUkZYkuR1TlS1KWtlKFdujwbIuaIqQhYgPPy7Z/Ddhy/xGqHeojI3f9e+AGn
L7XzEVxguluFx7C8CW+1PQfYvJY6gHURBFy1j40waK9wcbIxuIPg4IZQCgtNQNARogOlrYRYIYQo
jT4xJrW34oJwoJpFLWJV9JbkCrGJ2gSe7CPFH6dtNpNnz5YKzpU2yHm+g+2QYpsz3qbhvNA2oI/Z
lx1MK+QM71iCq/GVvS01lVFazrXVkVLVj22eFx6FzHL25JTkI3yls0qfGdtsXvWKtALKVlYY9ow5
I3lCwztxu4NAO06y4hv9eH2iQGeLhYpJVLCwZgGNyvcM6FOuIeiE712RTtjqqNeIFz40OSe+wPDa
TqnO2y6JVkMQ3slPBWZp+66GzkbnsZC2So+x8bYTs38gQn0vKU3xD8cyO4MzRl4/YuUsnXBJiQZh
MXW11AfnLC6rjYg81FhqpcsDbaz2qPT98MtZ7LdPnDpjekLJ/qLS29vi6W4Z3lnGMJbNTos+S+Zs
rUl6J9KVnPcX472Tre1/jGYWuyBJ73yNZBoBqyTJuSQZorBSeJm8q2THIqDl/0S96Gra01/Ak2Id
/Mj5HvyM5Cw23fEfx4+f3/fwu3KNkXDsrveMfR98FT7A1/Quuu8YoRKBRrmhge4SxEapHU3z0P69
VZoySYfBbmmuIV7SPD9hGu6yYJ9XWDrf
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
