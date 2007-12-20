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
        version="0.9.3dev",
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

    install_setuptools(py_executable)

    install_activate(home_dir, bin_dir)

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
    content = ('#!/usr/bin/env python\n'
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
FlWqXJpcICVYpGzx2OAY4oFsPpCLbjpQCLvZILVcXFaufi5cACHzOrI=
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
