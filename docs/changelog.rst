Release History
===============

.. include:: _draft.rst

.. towncrier release notes start

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
   history starts from there.
