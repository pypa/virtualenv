Release History
===============

.. include:: _draft.rst

.. towncrier release notes start

v20.0.8 (2020-03-04)
--------------------

Bugfixes - 20.0.8
~~~~~~~~~~~~~~~~~
- Having `distutils configuration <https://docs.python.org/3/install/index.html#distutils-configuration-files>`_
  files that set ``prefix`` and ``install_scripts`` cause installation of packages in the wrong location -
  by :user:`gaborbernat`. (`#1663 <https://github.com/pypa/virtualenv/issues/1663>`_)
- Fix ``PYTHONPATH`` being overriden on Python 2 — by :user:`jd`. (`#1673 <https://github.com/pypa/virtualenv/issues/1673>`_)
- Fix list configuration value parsing from config file or environment variable - by :user:`gaborbernat`. (`#1674 <https://github.com/pypa/virtualenv/issues/1674>`_)
- Fix Batch activation script shell prompt to display environment name by default - by :user:`spetafree`. (`#1679 <https://github.com/pypa/virtualenv/issues/1679>`_)
- Fix startup on Python 2 is slower for virtualenv - this was due to setuptools calculating it's working set distribution
  - by :user:`gaborbernat`. (`#1682 <https://github.com/pypa/virtualenv/issues/1682>`_)
- Fix entry points are not populated for editable installs on Python 2 due to setuptools working set being calculated
  before ``easy_install.pth`` runs - by :user:`gaborbernat`. (`#1684 <https://github.com/pypa/virtualenv/issues/1684>`_)
- Fix ``attr:`` import fails for setuptools - by :user:`gaborbernat`. (`#1685 <https://github.com/pypa/virtualenv/issues/1685>`_)


v20.0.7 (2020-02-26)
--------------------

Bugfixes - 20.0.7
~~~~~~~~~~~~~~~~~
- Disable distutils fixup for python 3 until `pypa/pip #7778 <https://github.com/pypa/pip/issues/7778>`_ is fixed and
  released - by :user:`gaborbernat`. (`#1669 <https://github.com/pypa/virtualenv/issues/1669>`_)


v20.0.6 (2020-02-26)
--------------------

Bugfixes - 20.0.6
~~~~~~~~~~~~~~~~~
- Fix global site package always being added with bundled macOs python framework builds - by :user:`gaborbernat`. (`#1561 <https://github.com/pypa/virtualenv/issues/1561>`_)
- Fix generated scripts use host version info rather than target - by :user:`gaborbernat`. (`#1600 <https://github.com/pypa/virtualenv/issues/1600>`_)
- Fix circular prefix reference with single elements (accept these as if they were system executables, print a info about
  them referencing themselves) - by :user:`gaborbernat`. (`#1632 <https://github.com/pypa/virtualenv/issues/1632>`_)
- Handle the case when the application data folder is read-only:

  - the application data folder is now controllable via :option:`app-data`,
  - :option:`clear-app-data` now cleans the entire application data folder, not just the ``app-data`` seeder path,
  - check if the application data path passed in does not exist or is read-only, and fallback to a temporary directory,
  - temporary directory application data is automatically cleaned up at the end of execution,
  - :option:`symlink-app-data` is always ``False`` when the application data is temporary

  by :user:`gaborbernat`. (`#1640 <https://github.com/pypa/virtualenv/issues/1640>`_)
- Fix PyPy 2 builtin modules are imported from standard library, rather than from builtin  - by :user:`gaborbernat`. (`#1652 <https://github.com/pypa/virtualenv/issues/1652>`_)
- Fix creation of entry points when path contains spaces - by :user:`nsoranzo`. (`#1660 <https://github.com/pypa/virtualenv/issues/1660>`_)
- Fix relative paths for the zipapp (for python ``3.7+``) - by :user:`gaborbernat`. (`#1666 <https://github.com/pypa/virtualenv/issues/1666>`_)

v20.0.5 (2020-02-21)
--------------------

Features - 20.0.5
~~~~~~~~~~~~~~~~~
- Also create ``pythonX.X`` executables when creating pypy virtualenvs - by :user:`asottile` (`#1612 <https://github.com/pypa/virtualenv/issues/1612>`_)
- Fail with better error message if trying to install source with unsupported ``setuptools``, allow ``setuptools-scm >= 2``
  and move to legacy ``setuptools-scm`` format to support better older platforms (``CentOS 7`` and such) - by :user:`gaborbernat`. (`#1621 <https://github.com/pypa/virtualenv/issues/1621>`_)
- Report of the created virtual environment is now split across four short lines rather than one long - by :user:`gaborbernat` (`#1641 <https://github.com/pypa/virtualenv/issues/1641>`_)

Bugfixes - 20.0.5
~~~~~~~~~~~~~~~~~
- Add macOs Python 2 Framework support (now we test it with the CI via brew) - by :user:`gaborbernat` (`#1561 <https://github.com/pypa/virtualenv/issues/1561>`_)
- Fix losing of libpypy-c.so when the pypy executable is a symlink - by :user:`asottile` (`#1614 <https://github.com/pypa/virtualenv/issues/1614>`_)
- Discover python interpreter in a case insensitive manner - by :user:`PrajwalM2212` (`#1624 <https://github.com/pypa/virtualenv/issues/1624>`_)
- Fix cross interpreter support when the host python sets ``sys.base_executable`` based on ``__PYVENV_LAUNCHER__`` -
  by :user:`cjolowicz` (`#1643 <https://github.com/pypa/virtualenv/issues/1643>`_)


v20.0.4 (2020-02-14)
--------------------

Features - 20.0.4
~~~~~~~~~~~~~~~~~
- When aliasing interpreters, use relative symlinks - by :user:`asottile`. (`#1596 <https://github.com/pypa/virtualenv/issues/1596>`_)

Bugfixes - 20.0.4
~~~~~~~~~~~~~~~~~
- Allow the use of ``/`` as pathname component separator on Windows - by ``vphilippon`` (`#1582 <https://github.com/pypa/virtualenv/issues/1582>`_)
- Lower minimal version of six required to 1.9 - by ``ssbarnea`` (`#1606 <https://github.com/pypa/virtualenv/issues/1606>`_)


v20.0.3 (2020-02-12)
--------------------

Bugfixes - 20.0.3
~~~~~~~~~~~~~~~~~
- On Python 2 with Apple Framework builds the global site package is no longer added when the
  :option:`system-site-packages` is not specified - by :user:`gaborbernat`. (`#1561 <https://github.com/pypa/virtualenv/issues/1561>`_)
- Fix system python discovery mechanism when prefixes contain relative parts (e.g. ``..``) by resolving paths within the
  python information query - by :user:`gaborbernat`. (`#1583 <https://github.com/pypa/virtualenv/issues/1583>`_)
- Expose a programmatic API as ``from virtualenv import cli_run`` - by :user:`gaborbernat`. (`#1585 <https://github.com/pypa/virtualenv/issues/1585>`_)
- Fix ``app-data`` :option:`seeder` injects a extra ``.dist-info.virtualenv`` path that breaks ``importlib.metadata``,
  now we inject an extra ``.virtualenv`` - by :user:`gaborbernat`. (`#1589 <https://github.com/pypa/virtualenv/issues/1589>`_)

Improved Documentation - 20.0.3
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
- Document a programmatic API as ``from virtualenv import cli_run`` under :ref:`programmatic_api` -
  by :user:`gaborbernat`. (`#1585 <https://github.com/pypa/virtualenv/issues/1585>`_)


v20.0.2 (2020-02-11)
--------------------

Features - 20.0.2
~~~~~~~~~~~~~~~~~
- Print out a one line message about the created virtual environment when no :option:`verbose` is set, this can now be
  silenced to get back the original behaviour via the :option:`quiet` flag - by :user:`pradyunsg`. (`#1557 <https://github.com/pypa/virtualenv/issues/1557>`_)
- Allow virtualenv's app data cache to be overridden by ``VIRTUALENV_OVERRIDE_APP_DATA`` - by :user:`asottile`. (`#1559 <https://github.com/pypa/virtualenv/issues/1559>`_)
- Passing in the virtual environment name/path is now required (no longer defaults to ``venv``) - by :user:`gaborbernat`. (`#1568 <https://github.com/pypa/virtualenv/issues/1568>`_)
- Add a CLI flag :option:`with-traceback` that allows displaying the stacktrace of the virtualenv when a failure occurs
  - by :user:`gaborbernat`. (`#1572 <https://github.com/pypa/virtualenv/issues/1572>`_)

Bugfixes - 20.0.2
~~~~~~~~~~~~~~~~~
- Support long path names for generated virtual environment console entry points (such as ``pip``) when using the
  ``app-data`` :option:`seeder` - by :user:`gaborbernat`. (`#997 <https://github.com/pypa/virtualenv/issues/997>`_)
- Improve python discovery mechanism:

  - do not fail if there are executables that fail to query (e.g. for not having execute access to it) on the ``PATH``,
  - beside the prefix folder also try with the platform dependent binary folder within that,

  by :user:`gaborbernat`. (`#1545 <https://github.com/pypa/virtualenv/issues/1545>`_)
- When copying (either files or trees) do not copy the permission bits, last access time, last modification time, and
  flags as access to these might be forbidden (for example in case of the macOs Framework Python) and these are not needed
  for the user to use the virtual environment - by :user:`gaborbernat`. (`#1561 <https://github.com/pypa/virtualenv/issues/1561>`_)
- While discovering a python executables interpreters that cannot be queried are now displayed with info level rather
  than warning, so now they're no longer shown by default (these can be just executables to which we don't have access
  or that are broken, don't warn if it's not the target Python we want) - by :user:`gaborbernat`. (`#1574 <https://github.com/pypa/virtualenv/issues/1574>`_)
- The ``app-data`` :option:`seeder` no longer symlinks the packages on UNIX and copies on Windows. Instead by default
  always copies, however now has the :option:`symlink-app-data` flag allowing users to request this less robust but faster
  method - by :user:`gaborbernat`. (`#1575 <https://github.com/pypa/virtualenv/issues/1575>`_)

Improved Documentation - 20.0.2
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
- Add link to the `legacy documentation <https://virtualenv.pypa.io/en/legacy>`_ for the changelog by :user:`jezdez`. (`#1547 <https://github.com/pypa/virtualenv/issues/1547>`_)
- Fine tune the documentation layout: default width of theme, allow tables to wrap around, soft corners for code snippets
  - by :user:`pradyunsg`. (`#1548 <https://github.com/pypa/virtualenv/issues/1548>`_)


v20.0.1 (2020-02-10)
--------------------

Features - 20.0.1
~~~~~~~~~~~~~~~~~
- upgrade embedded setuptools to ``45.2.0`` from ``45.1.0`` for Python ``3.4+`` - by :user:`gaborbernat`. (`#1554 <https://github.com/pypa/virtualenv/issues/1554>`_)

Bugfixes - 20.0.1
~~~~~~~~~~~~~~~~~
- Virtual environments created via relative path on Windows creates bad console executables - by :user:`gaborbernat`. (`#1552 <https://github.com/pypa/virtualenv/issues/1552>`_)
- Seems sometimes venvs created set their base executable to themselves; we accept these without question, so we handle
  virtual environments as system pythons causing issues - by :user:`gaborbernat`. (`#1553 <https://github.com/pypa/virtualenv/issues/1553>`_)


v20.0.0. (2020-02-10)
---------------------

Improved Documentation - 20.0.0.
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
- Fixes typos, repeated words and inconsistent heading spacing. Rephrase parts of the development documentation and CLI
  documentation. Expands shorthands like ``env var`` and ``config`` to their full forms. Uses descriptions from respective
  documentation, for projects listed in ``related links`` - by :user:`pradyunsg`. (`#1540 <https://github.com/pypa/virtualenv/issues/1540>`_)

v20.0.0b2 (2020-02-04)
----------------------

Features - 20.0.0b2
~~~~~~~~~~~~~~~~~~~
- Improve base executable discovery mechanism:

  - print at debug level why we refuse some candidates,
  - when no candidates match exactly, instead of hard failing fallback to the closest match where the priority of
    matching attributes is: python implementation, major version, minor version, architecture, patch version,
    release level and serial (this is to facilitate things to still work when the OS upgrade replace/upgrades the system
    python with a never version, than what the virtualenv host python was created with),
  - always resolve system_executable information during the interpreter discovery, and the discovered environment is the
    system interpreter instead of the venv/virtualenv (this happened before lazily the first time we accessed, and caused
    reporting that the created virtual environment is of type of the virtualenv host python version, instead of the
    system pythons version - these two can differ if the OS upgraded the system python underneath and the virtualenv
    host was created via copy),

  by :user:`gaborbernat`. (`#1515 <https://github.com/pypa/virtualenv/issues/1515>`_)
- Generate ``bash`` and ``fish`` activators on Windows too (as these can be available with git bash, cygwin or mysys2)
  - by :user:`gaborbernat`. (`#1527 <https://github.com/pypa/virtualenv/issues/1527>`_)
- Upgrade the bundled ``wheel`` package from ``0.34.0`` to ``0.34.2`` - by :user:`gaborbernat`. (`#1531 <https://github.com/pypa/virtualenv/issues/1531>`_)

Bugfixes - 20.0.0b2
~~~~~~~~~~~~~~~~~~~
- Bash activation script should have no extensions instead of ``.sh`` (this fixes the :pypi:`virtualenvwrapper`
  integration) - by :user:`gaborbernat`. (`#1508 <https://github.com/pypa/virtualenv/issues/1508>`_)
- Show less information when we run with a single verbosity (``-v``):

  - no longer shows accepted interpreters information (as the last proposed one is always the accepted one),
  - do not display the ``str_spec`` attribute for ``PythonSpec`` as these can be deduced from the other attributes,
  - for the ``app-data`` seeder do not show the type of lock, only the path to the app data directory,

  By :user:`gaborbernat`. (`#1510 <https://github.com/pypa/virtualenv/issues/1510>`_)
- Fixed cannot discover a python interpreter that has already been discovered under a different path (such is the case
  when we have multiple symlinks to the same interpreter) - by :user:`gaborbernat`. (`#1512 <https://github.com/pypa/virtualenv/issues/1512>`_)
- Support relative paths for ``-p`` - by :user:`gaborbernat`. (`#1514 <https://github.com/pypa/virtualenv/issues/1514>`_)
- Creating virtual environments in parallel fail with cannot acquire lock within app data - by :user:`gaborbernat`. (`#1516 <https://github.com/pypa/virtualenv/issues/1516>`_)
- pth files were not processed under Debian CPython2 interpreters - by :user:`gaborbernat`. (`#1517 <https://github.com/pypa/virtualenv/issues/1517>`_)
- Fix prompt not displayed correctly with upcoming fish 3.10 due to us not preserving ``$pipestatus`` - by
  :user:`krobelus`. (`#1530 <https://github.com/pypa/virtualenv/issues/1530>`_)
- Stable order within ``pyenv.cfg`` and add ``include-system-site-packages`` only for creators that reference a global
  Python - by user:`gaborbernat`. (`#1535 <https://github.com/pypa/virtualenv/issues/1535>`_)

Improved Documentation - 20.0.0b2
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
- Create the first iteration of the new documentation - by :user:`gaborbernat`. (`#1465 <https://github.com/pypa/virtualenv/issues/1465>`_)
- Project readme is now of type MarkDown instead of reStructuredText - by :user:`gaborbernat`. (`#1531 <https://github.com/pypa/virtualenv/issues/1531>`_)


v20.0.0b1 (2020-01-28)
----------------------

* First public release of the rewrite. Everything is brand new and just added.

.. warning::

   The current virtualenv is the second iteration of implementation. From version ``0.8`` all the way to ``16.7.9``
   we numbered the first iteration. Version ``20.0.0b1`` is a complete rewrite of the package, and as such this release
   history starts from there. The old changelog is still available in the
   `legacy branch documentation <https://virtualenv.pypa.io/en/legacy/changes.html>`_.
