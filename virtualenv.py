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
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
3CLIchL8H4rN4mY=
"""

      
if __name__ == '__main__':
    main()

