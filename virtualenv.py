"""Create a "virtual" Python installation
"""

import sys, os, optparse, shutil
join = os.path.join
py_version = 'python%s.%s' % (sys.version_info[0], sys.version_info[1])

## FIXME: probably other modules for Windows?
REQUIRED_MODULES = ['os', 're', 'posix', 'posixpath', 'stat', 'UserDict', 'readline',
                    'copy_reg', 'types', 'fnmatch',
                    'sre', 'sre_parse', 'sre_constants', 'sre_compile']

def mkdir(path):
    if not os.path.exists(path):
        print 'Creating %s' % path
        os.makedirs(path)
    else:
        if verbose:
            print 'Directory %s already exists' % path

def copyfile(src, dest):
    if not os.path.exists(src):
        # Some bad symlink in the src
        print 'Cannot find file %s' % src
        return
    if os.path.exists(dest):
        print 'File %s already exists' % dest
        return
    if hasattr(os, 'symlink'):
        if verbose:
            print 'Symlinking %s' % dest
        os.symlink(src, dest)
    else:
        if verbose:
            print 'Copying to %s' % dest
        if os.path.isdir(src):
            shutil.copytree(src, dest, True)
        else:
            shutil.copy2(src, dest)

def writefile(dest, content):
    if not os.path.exists(dest):
        if verbose:
            print 'Writing %s' % dest
        f = open(dest, 'wb')
        f.write(content)
        f.close()
        return
    else:
        f = open(dest, 'rb')
        c = f.read()
        f.close()
        if c != content:
            print 'Overwriting %s with new content' % dest
            f = open(dest, 'wb')
            f.write(content)
            f.close()
        elif verbose:
            print 'Content %s already in place' % dest

def rmtree(dir):
    if os.path.exists(dir):
        print 'Deleting tree %s' % dir
        shutil.rmtree(dir)
    else:
        if verbose:
            print 'Do not need to delete %s; already gone' % dir

def make_exe(fn):
    if os.name == 'posix':
        oldmode = os.stat(fn).st_mode & 07777
        newmode = (oldmode | 0555) & 07777
        os.chmod(fn, newmode)
        if verbose:
            print 'Changed mode of %s to %s' % (fn, oct(newmode))

parser = optparse.OptionParser(
    usage="%prog [OPTIONS] DEST_DIR")

parser.add_option(
    '-v', '--verbose',
    action='count',
    dest='verbose',
    default=0,
    help="Increase verbosity")

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

def main():
    options, args = parser.parse_args()
    global verbose
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
    lib_dir = join(home_dir, 'lib', py_version)
    inc_dir = join(home_dir, 'include', py_version)
    bin_dir = join(home_dir, 'bin')

    if sys.executable.startswith(bin_dir):
        print 'Please use the *system* python to run this script'
        return

    verbose = options.verbose
        
    if options.clear:
        rmtree(lib_dir)
        rmtree(inc_dir)
        print 'Not deleting', bin_dir

    prefix = sys.prefix
    mkdir(lib_dir)
    stdlib_dir = join(prefix, 'lib', py_version)
    for fn in os.listdir(stdlib_dir):
        if fn != 'site-packages' and os.path.splitext(fn)[0] in REQUIRED_MODULES:
            copyfile(join(stdlib_dir, fn), join(lib_dir, fn))
    writefile(join(lib_dir, 'site.py'), SITE_PY)
    writefile(join(stdlib_dir, 'orig-prefix.txt'), prefix)
    if options.no_site_packages:
        writefile(join(stdlib_dir, 'no-global-site-packages.txt'), '')

    #mkdir(inc_dir)
    #stdinc_dir = join(prefix, 'include', py_version)
    #for fn in os.listdir(stdinc_dir):
    #    copyfile(join(stdinc_dir, fn), join(inc_dir, fn))

    if sys.exec_prefix != sys.prefix:
        exec_dir = join(sys.exec_prefix, 'lib', py_version)
        for fn in os.listdir(exec_dir):
            copyfile(join(exec_dir, fn), join(lib_dir, fn))

    mkdir(bin_dir)
    print 'Copying %s to %s' % (sys.executable, bin_dir)
    py_executable = join(bin_dir, 'python')
    if sys.executable != py_executable:
        shutil.copyfile(sys.executable, py_executable)
        make_exe(py_executable)

    pydistutils = os.path.expanduser('~/.pydistutils.cfg')
    if os.path.exists(pydistutils):
        print 'Please make sure you remove any previous custom paths from'
        print "your", pydistutils, "file."

    print "You're now ready to download ez_setup.py, and run"
    print py_executable, "ez_setup.py"

##file site.py
SITE_PY = """
"""

      
if __name__ == '__main__':
    main()

