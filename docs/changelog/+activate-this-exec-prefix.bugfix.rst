Point ``sys.exec_prefix`` at the environment when ``activate_this.py`` activates it, as ``sys.prefix`` already is.
Before, ``sysconfig`` kept the ``platlib`` path at the base Python on POSIX, so pip in the activated process installed
compiled packages into the system ``site-packages`` instead of the environment.
