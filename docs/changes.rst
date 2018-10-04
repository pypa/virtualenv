Release History
===============

16.1.0 (unreleased)
-------------------

* Fixed documentation to use pypi.org and correct curl options; :issue:`1042`

16.0.0 (2018-05-16)
-------------------

* Drop support for Python 2.6.

* Upgrade pip to 10.0.1.

* Upgrade setuptools to 39.1.0.

* Upgrade wheel to 0.31.1.


15.2.0 (2018-03-21)
-------------------

* Upgrade setuptools to 39.0.1.

* Upgrade pip to 9.0.3.

* Upgrade wheel to 0.30.0.


15.1.0 (2016-11-15)
-------------------

* Support Python 3.6.

* Upgrade setuptools to 28.0.0.

* Upgrade pip to 9.0.1.

* Don't install pre-release versions of pip, setuptools, or wheel from PyPI.


15.0.3 (2016-08-05)
-------------------

* Test for given python path actually being an executable *file*, :issue:`939`

* Only search for copy actual existing Tcl/Tk directories (:pull:`937`)

* Generically search for correct Tcl/Tk version (:pull:`926`, :pull:`933`)

* Upgrade setuptools to 22.0.5

15.0.2 (2016-05-28)
-------------------

* Copy Tcl/Tk libs on Windows to allow them to run,
  fixes :issue:`93` (:pull:`888`)

* Upgrade setuptools to 21.2.1.

* Upgrade pip to 8.1.2.


15.0.1 (2016-03-17)
-------------------

* Print error message when DEST_DIR exists and is a file

* Upgrade setuptools to 20.3

* Upgrade pip to 8.1.1.


15.0.0 (2016-03-05)
-------------------

* Remove the `virtualenv-N.N` script from the package; this can no longer be
  correctly created from a wheel installation.
  Resolves :issue:`851`, :issue:`692`

* Remove accidental runtime dependency on pip by extracting certificate in the
  subprocess.

* Upgrade setuptools 20.2.2.

* Upgrade pip to 8.1.0.


14.0.6 (2016-02-07)
-------------------

* Upgrade setuptools to 20.0

* Upgrade wheel to 0.29.0

* Fix an error where virtualenv didn't pass in a working ssl certificate for
  pip, causing "weird" errors related to ssl.


14.0.5 (2016-02-01)
-------------------

* Homogenize drive letter casing for both prefixes and filenames. :issue:`858`


14.0.4 (2016-01-31)
-------------------

* Upgrade setuptools to 19.6.2

* Revert ac4ea65; only correct drive letter case.
  Fixes :issue:`856`, :issue:`815`


14.0.3 (2016-01-28)
-------------------

* Upgrade setuptools to 19.6.1


14.0.2 (2016-01-28)
-------------------

* Upgrade setuptools to 19.6

* Supress any errors from `unset` on different shells (:pull:`843`)

* Normalize letter case for prefix path checking. Fixes :issue:`837`


14.0.1 (2016-01-21)
-------------------

* Upgrade from pip 8.0.0 to 8.0.2.

* Fix the default of ``--(no-)download`` to default to downloading.


14.0.0 (2016-01-19)
-------------------

* **BACKWARDS INCOMPATIBLE** Drop support for Python 3.2.

* Upgrade setuptools to 19.4

* Upgrade wheel to 0.26.0

* Upgrade pip to 8.0.0

* Upgrade argparse to 1.4.0

* Added support for ``python-config`` script (:pull:`798`)

* Updated activate.fish (:pull:`589`) (:pull:`799`)

* Account for a ``site.pyo`` correctly in some python implementations (:pull:`759`)

* Properly restore an empty PS1 (:issue:`407`)

* Properly remove ``pydoc`` when deactivating

* Remove workaround for very old Mageia / Mandriva linuxes (:pull:`472`)

* Added a space after virtualenv name in the prompt: ``(env) $PS1``

* Make sure not to run a --user install when creating the virtualenv (:pull:`803`)

* Remove virtualenv.py's path from sys.path when executing with a new
  python. Fixes issue :issue:`779`, :issue:`763` (:pull:`805`)

* Remove use of () in .bat files so ``Program Files (x86)`` works :issue:`35`

* Download new releases of the preinstalled software from PyPI when there are
  new releases available. This behavior can be disabled using
  ``--no-download``.

* Make ``--no-setuptools``, ``--no-pip``, and ``--no-wheel`` independent of
  each other.


13.1.2 (2015-08-23)
-------------------

* Upgrade pip to 7.1.2.


13.1.1 (2015-08-20)
-------------------

* Upgrade pip to 7.1.1.

* Upgrade setuptools to 18.2.

* Make the activate script safe to use when bash is running with ``-u``.


13.1.0 (2015-06-30)
-------------------

* Upgrade pip to 7.1.0

* Upgrade setuptools to 18.0.1


13.0.3 (2015-06-01)
-------------------

* Upgrade pip to 7.0.3


13.0.2 (2015-06-01)
-------------------

* Upgrade pip to 7.0.2

* Upgrade setuptools to 17.0


13.0.1 (2015-05-22)
-------------------

* Upgrade pip to 7.0.1


13.0.0 (2015-05-21)
-------------------

* Automatically install wheel when creating a new virutalenv. This can be
  disabled by using the ``--no-wheel`` option.

* Don't trust the current directory as a location to discover files to install
  packages from.

* Upgrade setuptools to 16.0.

* Upgrade pip to 7.0.0.


12.1.1 (2015-04-07)
-------------------

* Upgrade pip to 6.1.1


12.1.0 (2015-04-07)
-------------------

* Upgrade setuptools to 15.0

* Upgrade pip to 6.1.0


12.0.7 (2015-02-04)
-------------------

* Upgrade pip to 6.0.8


12.0.6 (2015-01-28)
-------------------

* Upgrade pip to 6.0.7

* Upgrade setuptools to 12.0.5


12.0.5 (2015-01-03)
-------------------

* Upgrade pip to 6.0.6

* Upgrade setuptools to 11.0


12.0.4 (2014-12-23)
-------------------

* Revert the fix to ``-p`` on Debian based pythons as it was broken in other
  situations.

* Revert several sys.path changes new in 12.0 which were breaking virtualenv.

12.0.3 (2014-12-23)
-------------------

* Fix an issue where Debian based Pythons would fail when using -p with the
  host Python.

* Upgrade pip to 6.0.3

12.0.2 (2014-12-23)
-------------------

* Upgraded pip to 6.0.2

12.0.1 (2014-12-22)
-------------------

* Upgraded pip to 6.0.1


12.0 (2014-12-22)
-----------------

* **PROCESS** Version numbers are now simply ``X.Y`` where the leading ``1``
  has been dropped.
* Split up documentation into structured pages
* Now using pytest framework
* Correct sys.path ordering for debian, issue #461
* Correctly throws error on older Pythons, issue #619
* Allow for empty $PATH, pull #601
* Don't set prompt if $env:VIRTUAL_ENV_DISABLE_PROMPT is set for Powershell
* Updated setuptools to 7.0

1.11.6 (2014-05-16)
-------------------

* Updated setuptools to 3.6
* Updated pip to 1.5.6

1.11.5 (2014-05-03)
-------------------

* Updated setuptools to 3.4.4
* Updated documentation to use https://virtualenv.pypa.io/
* Updated pip to 1.5.5

1.11.4 (2014-02-21)
-------------------

* Updated pip to 1.5.4


1.11.3 (2014-02-20)
-------------------

* Updated setuptools to 2.2
* Updated pip to 1.5.3


1.11.2 (2014-01-26)
-------------------

* Fixed easy_install installed virtualenvs by updated pip to 1.5.2

1.11.1 (2014-01-20)
-------------------

* Fixed an issue where pip and setuptools were not getting installed when using
  the ``--system-site-packages`` flag.
* Updated setuptools to fix an issue when installed with easy_install
* Fixed an issue with Python 3.4 and sys.stdout encoding being set to ascii
* Upgraded pip to v1.5.1
* Upgraded setuptools to v2.1

1.11 (2014-01-02)
-----------------

* **BACKWARDS INCOMPATIBLE** Switched to using wheels for the bundled copies of
  setuptools and pip. Using sdists is no longer supported - users supplying
  their own versions of pip/setuptools will need to provide wheels.
* **BACKWARDS INCOMPATIBLE** Modified the handling of ``--extra-search-dirs``.
  This option now works like pip's ``--find-links`` option, in that it adds
  extra directories to search for compatible wheels for pip and setuptools.
  The actual wheel selected is chosen based on version and compatibility, using
  the same algorithm as ``pip install setuptools``.
* Fixed #495, --always-copy was failing (#PR 511)
* Upgraded pip to v1.5
* Upgraded setuptools to v1.4

1.10.1 (2013-08-07)
-------------------

* **New Signing Key** Release 1.10.1 is using a different key than normal with
  fingerprint: 7C6B 7C5D 5E2B 6356 A926 F04F 6E3C BCE9 3372 DCFA
* Upgraded pip to v1.4.1
* Upgraded setuptools to v0.9.8


1.10 (2013-07-23)
-----------------

* **BACKWARDS INCOMPATIBLE** Dropped support for Python 2.5. The minimum
  supported Python version is now Python 2.6.

* **BACKWARDS INCOMPATIBLE** Using ``virtualenv.py`` as an isolated script
  (i.e. without an associated ``virtualenv_support`` directory) is no longer
  supported for security reasons and will fail with an error.

  Along with this, ``--never-download`` is now always pinned to ``True``, and
  is only being maintained in the short term for backward compatibility
  (Pull #412).

* **IMPORTANT** Switched to the new setuptools (v0.9.7) which has been merged
  with Distribute_ again and works for Python 2 and 3 with one codebase.
  The ``--distribute`` and ``--setuptools`` options are now no-op.

* Updated to pip 1.4.

* Added support for PyPy3k

* Added the option to use a version number with the ``-p`` option to get the
  system copy of that Python version (Windows only)

* Removed embedded ``ez_setup.py``, ``distribute_setup.py`` and
  ``distribute_from_egg.py`` files as part of switching to merged setuptools.

* Fixed ``--relocatable`` to work better on Windows.

* Fixed issue with readline on Windows.

.. _Distribute: https://pypi.org/project/distribute

1.9.1 (2013-03-08)
------------------

* Updated to pip 1.3.1 that fixed a major backward incompatible change of
  parsing URLs to externally hosted packages that got accidentily included
  in pip 1.3.

1.9 (2013-03-07)
----------------

* Unset VIRTUAL_ENV environment variable in deactivate.bat (Pull #364)
* Upgraded distribute to 0.6.34.
* Added ``--no-setuptools`` and ``--no-pip`` options (Pull #336).
* Fixed Issue #373. virtualenv-1.8.4 was failing in cygwin (Pull #382).
* Fixed Issue #378. virtualenv is now "multiarch" aware on debian/ubuntu (Pull #379).
* Fixed issue with readline module path on pypy and OSX (Pull #374).
* Made 64bit detection compatible with Python 2.5 (Pull #393).


1.8.4 (2012-11-25)
------------------

* Updated distribute to 0.6.31. This fixes #359 (numpy install regression) on
  UTF-8 platforms, and provides a workaround on other platforms:
  ``PYTHONIOENCODING=utf8 pip install numpy``.

* When installing virtualenv via curl, don't forget to filter out arguments
  the distribute setup script won't understand. Fixes #358.

* Added some more integration tests.

* Removed the unsupported embedded setuptools egg for Python 2.4 to reduce
  file size.

1.8.3 (2012-11-21)
------------------

* Fixed readline on OS X. Thanks minrk

* Updated distribute to 0.6.30 (improves our error reporting, plus new
  distribute features and fixes). Thanks Gabriel (g2p)

* Added compatibility with multiarch Python (Python 3.3 for example). Added an
  integration test. Thanks Gabriel (g2p)

* Added ability to install distribute from a user-provided egg, rather than the
  bundled sdist, for better speed. Thanks Paul Moore.

* Make the creation of lib64 symlink smarter about already-existing symlink,
  and more explicit about full paths. Fixes #334 and #330. Thanks Jeremy Orem.

* Give lib64 site-dir preference over lib on 64-bit systems, to avoid wrong
  32-bit compiles in the venv. Fixes #328. Thanks Damien Nozay.

* Fix a bug with prompt-handling in ``activate.csh`` in non-interactive csh
  shells. Fixes #332. Thanks Benjamin Root for report and patch.

* Make it possible to create a virtualenv from within a Python
  3.3. pyvenv. Thanks Chris McDonough for the report.

* Add optional --setuptools option to be able to switch to it in case
  distribute is the default (like in Debian).

1.8.2 (2012-09-06)
------------------

* Updated the included pip version to 1.2.1 to fix regressions introduced
  there in 1.2.


1.8.1 (2012-09-03)
------------------

* Fixed distribute version used with `--never-download`. Thanks michr for
  report and patch.

* Fix creating Python 3.3 based virtualenvs by unsetting the
  ``__PYVENV_LAUNCHER__`` environment variable in subprocesses.


1.8 (2012-09-01)
----------------

* **Dropped support for Python 2.4** The minimum supported Python version is
  now Python 2.5.

* Fix `--relocatable` on systems that use lib64. Fixes #78. Thanks Branden
  Rolston.

* Symlink some additional modules under Python 3. Fixes #194. Thanks Vinay
  Sajip, Ian Clelland, and Stefan Holek for the report.

* Fix ``--relocatable`` when a script uses ``__future__`` imports. Thanks
  Branden Rolston.

* Fix a bug in the config option parser that prevented setting negative
  options with environment variables. Thanks Ralf Schmitt.

* Allow setting ``--no-site-packages`` from the config file.

* Use ``/usr/bin/multiarch-platform`` if available to figure out the include
  directory. Thanks for the patch, Mika Laitio.

* Fix ``install_name_tool`` replacement to work on Python 3.X.

* Handle paths of users' site-packages on Mac OS X correctly when changing
  the prefix.

* Updated the embedded version of distribute to 0.6.28 and pip to 1.2.


1.7.2 (2012-06-22)
------------------

* Updated to distribute 0.6.27.

* Fix activate.fish on OS X. Fixes #8. Thanks David Schoonover.

* Create a virtualenv-x.x script with the Python version when installing, so
  virtualenv for multiple Python versions can be installed to the same
  script location. Thanks Miki Tebeka.

* Restored ability to create a virtualenv with a path longer than 78
  characters, without breaking creation of virtualenvs with non-ASCII paths.
  Thanks, Bradley Ayers.

* Added ability to create virtualenvs without having installed Apple's
  developers tools (using an own implementation of ``install_name_tool``).
  Thanks Mike Hommey.

* Fixed PyPy and Jython support on Windows. Thanks Konstantin Zemlyak.

* Added pydoc script to ease use. Thanks Marc Abramowitz. Fixes #149.

* Fixed creating a bootstrap script on Python 3. Thanks Raul Leal. Fixes #280.

* Fixed inconsistency when having set the ``PYTHONDONTWRITEBYTECODE`` env var
  with the --distribute option or the ``VIRTUALENV_USE_DISTRIBUTE`` env var.
  ``VIRTUALENV_USE_DISTRIBUTE`` is now considered again as a legacy alias.


1.7.1.2 (2012-02-17)
--------------------

* Fixed minor issue in `--relocatable`. Thanks, Cap Petschulat.


1.7.1.1 (2012-02-16)
--------------------

* Bumped the version string in ``virtualenv.py`` up, too.

* Fixed rST rendering bug of long description.


1.7.1 (2012-02-16)
------------------

* Update embedded pip to version 1.1.

* Fix `--relocatable` under Python 3. Thanks Doug Hellmann.

* Added environ PATH modification to activate_this.py. Thanks Doug
  Napoleone. Fixes #14.

* Support creating virtualenvs directly from a Python build directory on
  Windows. Thanks CBWhiz. Fixes #139.

* Use non-recursive symlinks to fix things up for posix_local install
  scheme. Thanks michr.

* Made activate script available for use with msys and cygwin on Windows.
  Thanks Greg Haskins, Cliff Xuan, Jonathan Griffin and Doug Napoleone.
  Fixes #176.

* Fixed creation of virtualenvs on Windows when Python is not installed for
  all users. Thanks Anatoly Techtonik for report and patch and Doug
  Napoleone for testing and confirmation. Fixes #87.

* Fixed creation of virtualenvs using -p in installs where some modules
  that ought to be in the standard library (e.g. `readline`) are actually
  installed in `site-packages` next to `virtualenv.py`. Thanks Greg Haskins
  for report and fix. Fixes #167.

* Added activation script for Powershell (signed by Jannis Leidel). Many
  thanks to Jason R. Coombs.


1.7 (2011-11-30)
----------------

* Gave user-provided ``--extra-search-dir`` priority over default dirs for
  finding setuptools/distribute (it already had priority for finding pip).
  Thanks Ethan Jucovy.

* Updated embedded Distribute release to 0.6.24. Thanks Alex Gronholm.

* Made ``--no-site-packages`` behavior the default behavior.  The
  ``--no-site-packages`` flag is still permitted, but displays a warning when
  used. Thanks Chris McDonough.

* New flag: ``--system-site-packages``; this flag should be passed to get the
  previous default global-site-package-including behavior back.

* Added ability to set command options as environment variables and options
  in a ``virtualenv.ini`` file.

* Fixed various encoding related issues with paths. Thanks Gunnlaugur Thor Briem.

* Made ``virtualenv.py`` script executable.


1.6.4 (2011-07-21)
------------------

* Restored ability to run on Python 2.4, too.


1.6.3 (2011-07-16)
------------------

* Restored ability to run on Python < 2.7.


1.6.2 (2011-07-16)
------------------

* Updated embedded distribute release to 0.6.19.

* Updated embedded pip release to 1.0.2.

* Fixed #141 - Be smarter about finding pkg_resources when using the
  non-default Python interpreter (by using the ``-p`` option).

* Fixed #112 - Fixed path in docs.

* Fixed #109 - Corrected doctests of a Logger method.

* Fixed #118 - Fixed creating virtualenvs on platforms that use the
  "posix_local" install scheme, such as Ubuntu with Python 2.7.

* Add missing library to Python 3 virtualenvs (``_dummy_thread``).


1.6.1 (2011-04-30)
------------------

* Start to use git-flow.

* Added support for PyPy 1.5

* Fixed #121 -- added sanity-checking of the -p argument. Thanks Paul Nasrat.

* Added progress meter for pip installation as well as setuptools. Thanks Ethan
  Jucovy.

* Added --never-download and --search-dir options. Thanks Ethan Jucovy.


1.6
---

* Added Python 3 support! Huge thanks to Vinay Sajip and Vitaly Babiy.

* Fixed creation of virtualenvs on Mac OS X when standard library modules
  (readline) are installed outside the standard library.

* Updated bundled pip to 1.0.


1.5.2
-----

* Moved main repository to Github: https://github.com/pypa/virtualenv

* Transferred primary maintenance from Ian to Jannis Leidel, Carl Meyer and Brian Rosner

* Fixed a few more pypy related bugs.

* Updated bundled pip to 0.8.2.

* Handed project over to new team of maintainers.

* Moved virtualenv to Github at https://github.com/pypa/virtualenv


1.5.1
-----

* Added ``_weakrefset`` requirement for Python 2.7.1.

* Fixed Windows regression in 1.5


1.5
---

* Include pip 0.8.1.

* Add support for PyPy.

* Uses a proper temporary dir when installing environment requirements.

* Add ``--prompt`` option to be able to override the default prompt prefix.

* Fix an issue with ``--relocatable`` on Windows.

* Fix issue with installing the wrong version of distribute.

* Add fish and csh activate scripts.


1.4.9
-----

* Include pip 0.7.2


1.4.8
-----

* Fix for Mac OS X Framework builds that use
  ``--universal-archs=intel``

* Fix ``activate_this.py`` on Windows.

* Allow ``$PYTHONHOME`` to be set, so long as you use ``source
  bin/activate`` it will get unset; if you leave it set and do not
  activate the environment it will still break the environment.

* Include pip 0.7.1


1.4.7
-----

* Include pip 0.7


1.4.6
-----

* Allow ``activate.sh`` to skip updating the prompt (by setting
  ``$VIRTUAL_ENV_DISABLE_PROMPT``).


1.4.5
-----

* Include pip 0.6.3

* Fix ``activate.bat`` and ``deactivate.bat`` under Windows when
  ``PATH`` contained a parenthesis


1.4.4
-----

* Include pip 0.6.2 and Distribute 0.6.10

* Create the ``virtualenv`` script even when Setuptools isn't
  installed

* Fix problem with ``virtualenv --relocate`` when ``bin/`` has
  subdirectories (e.g., ``bin/.svn/``); from Alan Franzoni.

* If you set ``$VIRTUALENV_DISTRIBUTE`` then virtualenv will use
  Distribute by default (so you don't have to remember to use
  ``--distribute``).


1.4.3
-----

* Include pip 0.6.1


1.4.2
-----

* Fix pip installation on Windows

* Fix use of stand-alone ``virtualenv.py`` (and boot scripts)

* Exclude ~/.local (user site-packages) from environments when using
  ``--no-site-packages``


1.4.1
-----

* Include pip 0.6


1.4
---

* Updated setuptools to 0.6c11

* Added the --distribute option

* Fixed packaging problem of support-files


1.3.4
-----

* Virtualenv now copies the actual embedded Python binary on
  Mac OS X to fix a hang on Snow Leopard (10.6).

* Fail more gracefully on Windows when ``win32api`` is not installed.

* Fix site-packages taking precedent over Jython's ``__classpath__``
  and also specially handle the new ``__pyclasspath__`` entry in
  ``sys.path``.

* Now copies Jython's ``registry`` file to the virtualenv if it exists.

* Better find libraries when compiling extensions on Windows.

* Create ``Scripts\pythonw.exe`` on Windows.

* Added support for the Debian/Ubuntu
  ``/usr/lib/pythonX.Y/dist-packages`` directory.

* Set ``distutils.sysconfig.get_config_vars()['LIBDIR']`` (based on
  ``sys.real_prefix``) which is reported to help building on Windows.

* Make ``deactivate`` work on ksh

* Fixes for ``--python``: make it work with ``--relocatable`` and the
  symlink created to the exact Python version.


1.3.3
-----

* Use Windows newlines in ``activate.bat``, which has been reported to help
  when using non-ASCII directory names.

* Fixed compatibility with Jython 2.5b1.

* Added a function ``virtualenv.install_python`` for more fine-grained
  access to what ``virtualenv.create_environment`` does.

* Fix `a problem <https://bugs.launchpad.net/virtualenv/+bug/241581>`_
  with Windows and paths that contain spaces.

* If ``/path/to/env/.pydistutils.cfg`` exists (or
  ``/path/to/env/pydistutils.cfg`` on Windows systems) then ignore
  ``~/.pydistutils.cfg`` and use that other file instead.

* Fix ` a problem
  <https://bugs.launchpad.net/virtualenv/+bug/340050>`_ picking up
  some ``.so`` libraries in ``/usr/local``.


1.3.2
-----

* Remove the ``[install] prefix = ...`` setting from the virtualenv
  ``distutils.cfg`` -- this has been causing problems for a lot of
  people, in rather obscure ways.

* If you use a boot script it will attempt to import ``virtualenv``
  and find a pre-downloaded Setuptools egg using that.

* Added platform-specific paths, like ``/usr/lib/pythonX.Y/plat-linux2``


1.3.1
-----

* Real Python 2.6 compatibility.  Backported the Python 2.6 updates to
  ``site.py``, including `user directories
  <http://docs.python.org/dev/whatsnew/2.6.html#pep-370-per-user-site-packages-directory>`_
  (this means older versions of Python will support user directories,
  whether intended or not).

* Always set ``[install] prefix`` in ``distutils.cfg`` -- previously
  on some platforms where a system-wide ``distutils.cfg`` was present
  with a ``prefix`` setting, packages would be installed globally
  (usually in ``/usr/local/lib/pythonX.Y/site-packages``).

* Sometimes Cygwin seems to leave ``.exe`` off ``sys.executable``; a
  workaround is added.

* Fix ``--python`` option.

* Fixed handling of Jython environments that use a
  jython-complete.jar.


1.3
---

* Update to Setuptools 0.6c9
* Added an option ``virtualenv --relocatable EXISTING_ENV``, which
  will make an existing environment "relocatable" -- the paths will
  not be absolute in scripts, ``.egg-info`` and ``.pth`` files.  This
  may assist in building environments that can be moved and copied.
  You have to run this *after* any new packages installed.
* Added ``bin/activate_this.py``, a file you can use like
  ``execfile("path_to/activate_this.py",
  dict(__file__="path_to/activate_this.py"))`` -- this will activate
  the environment in place, similar to what `the mod_wsgi example
  does <http://code.google.com/p/modwsgi/wiki/VirtualEnvironments>`_.
* For Mac framework builds of Python, the site-packages directory
  ``/Library/Python/X.Y/site-packages`` is added to ``sys.path``, from
  Andrea Rech.
* Some platform-specific modules in Macs are added to the path now
  (``plat-darwin/``, ``plat-mac/``, ``plat-mac/lib-scriptpackages``),
  from Andrea Rech.
* Fixed a small Bashism in the ``bin/activate`` shell script.
* Added ``__future__`` to the list of required modules, for Python
  2.3.  You'll still need to backport your own ``subprocess`` module.
* Fixed the ``__classpath__`` entry in Jython's ``sys.path`` taking
  precedent over virtualenv's libs.


1.2
---

* Added a ``--python`` option to select the Python interpreter.
* Add ``warnings`` to the modules copied over, for Python 2.6 support.
* Add ``sets`` to the module copied over for Python 2.3 (though Python
  2.3 still probably doesn't work).


1.1.1
-----

* Added support for Jython 2.5.


1.1
---

* Added support for Python 2.6.
* Fix a problem with missing ``DLLs/zlib.pyd`` on Windows.  Create
* ``bin/python`` (or ``bin/python.exe``) even when you run virtualenv
  with an interpreter named, e.g., ``python2.4``
* Fix MacPorts Python
* Added --unzip-setuptools option
* Update to Setuptools 0.6c8
* If the current directory is not writable, run ez_setup.py in ``/tmp``
* Copy or symlink over the ``include`` directory so that packages will
  more consistently compile.


1.0
---

* Fix build on systems that use ``/usr/lib64``, distinct from
  ``/usr/lib`` (specifically CentOS x64).
* Fixed bug in ``--clear``.
* Fixed typos in ``deactivate.bat``.
* Preserve ``$PYTHONPATH`` when calling subprocesses.


0.9.2
-----

* Fix include dir copying on Windows (makes compiling possible).
* Include the main ``lib-tk`` in the path.
* Patch ``distutils.sysconfig``: ``get_python_inc`` and
  ``get_python_lib`` to point to the global locations.
* Install ``distutils.cfg`` before Setuptools, so that system
  customizations of ``distutils.cfg`` won't effect the installation.
* Add ``bin/pythonX.Y`` to the virtualenv (in addition to
  ``bin/python``).
* Fixed an issue with Mac Framework Python builds, and absolute paths
  (from Ronald Oussoren).


0.9.1
-----

* Improve ability to create a virtualenv from inside a virtualenv.
* Fix a little bug in ``bin/activate``.
* Actually get ``distutils.cfg`` to work reliably.


0.9
---

* Added ``lib-dynload`` and ``config`` to things that need to be
  copied over in an environment.
* Copy over or symlink the ``include`` directory, so that you can
  build packages that need the C headers.
* Include a ``distutils`` package, so you can locally update
  ``distutils.cfg`` (in ``lib/pythonX.Y/distutils/distutils.cfg``).
* Better avoid downloading Setuptools, and hitting PyPI on environment
  creation.
* Fix a problem creating a ``lib64/`` directory.
* Should work on MacOSX Framework builds (the default Python
  installations on Mac).  Thanks to Ronald Oussoren.


0.8.4
-----

* Windows installs would sometimes give errors about ``sys.prefix`` that
  were inaccurate.
* Slightly prettier output.


0.8.3
-----

* Added support for Windows.


0.8.2
-----

* Give a better warning if you are on an unsupported platform (Mac
  Framework Pythons, and Windows).
* Give error about running while inside a workingenv.
* Give better error message about Python 2.3.


0.8.1
-----

Fixed packaging of the library.


0.8
---

Initial release.  Everything is changed and new!
