Installation
============

via pipx
--------

:pypi:`virtualenv` is a CLI tool that needs a Python interpreter to run. If you already have a ``Python 3.5+``
interpreter the best is to use :pypi:`pipx` to install virtualenv into an isolated environment. This has the added
benefit that later you'll be able to upgrade virtualenv without affecting other parts of the system.

.. code-block:: console

    pipx install virtualenv
    virtualenv --help

via pip
-------

Alternatively you can install it within the global Python interpreter itself (perhaps as a user package via the
``--user`` flag). Be cautious if you are using a python install that is managed by your operating system or
another package manager. ``pip`` might not coordinate with those tools, and may leave your system in an
inconsistent state. Note, if you go down this path you need to ensure pip is new enough per the subsections below:

.. code-block:: console

    python -m pip install --user virtualenv
    python -m virtualenv --help

wheel
~~~~~
Installing virtualenv via a wheel (default with pip) requires an installer that can understand the ``python-requires``
tag (see `PEP-503 <https://www.python.org/dev/peps/pep-0503/>`_), with pip this is version ``9.0.0`` (released 2016
November). Furthermore, in case you're not installing it via the PyPi you need to be using a mirror that correctly
forwards the ``python-requires`` tag (notably the OpenStack mirrors don't do this, or older
`devpi <https://github.com/devpi/devpi>`_ versions - added with version ``4.7.0``).

.. _sdist:

sdist
~~~~~
When installing via a source distribution you need an installer that handles the
`PEP-517 <https://www.python.org/dev/peps/pep-0517/>`_ specification. In case of ``pip`` this is version ``18.0.0`` or
later (released on 2018 July). If you cannot upgrade your pip to support this you need to ensure that the build
requirements from `pyproject.toml <https://github.com/pypa/virtualenv/blob/main/pyproject.toml#L2>`_ are satisfied
before triggering the install.

via zipapp
----------

You can use virtualenv without installing it too. We publish a Python
`zipapp <https://docs.python.org/3/library/zipapp.html>`_, you can just download this from
`https://bootstrap.pypa.io/virtualenv.pyz <https://bootstrap.pypa.io/virtualenv.pyz>`_ and invoke this package
with a python interpreter:

.. code-block:: console

    python virtualenv.pyz --help

The root level zipapp is always the current latest release. To get the last supported zipapp against a given python
minor release use the link ``https://bootstrap.pypa.io/virtualenv/x.y/virtualenv.pyz``, e.g. for the last virtualenv
supporting Python 2.7 use
`https://bootstrap.pypa.io/virtualenv/2.7/virtualenv.pyz <https://bootstrap.pypa.io/virtualenv/2.7/virtualenv.pyz>`_.

If you are looking for past version of virtualenv.pyz they are available here:
https://github.com/pypa/get-virtualenv/blob/<virtualenv version>/public/<python version>/virtualenv.pyz?raw=true

via ``setup.py``
----------------
We don't recommend and officially support this method. One should prefer using an installer that supports
`PEP-517 <https://www.python.org/dev/peps/pep-0517/>`_ interface, such as pip ``19.0.0`` or later. That being said you
might be able to still install a package via this method if you satisfy build dependencies before calling the install
command (as described under :ref:`sdist`).

latest unreleased
-----------------
Installing an unreleased version is discouraged and should be only done for testing purposes. If you do so you'll need
a pip version of at least ``18.0.0`` and use the following command:


.. code-block:: console

    pip install git+https://github.com/pypa/virtualenv.git@main

.. _compatibility-requirements:

Python and OS Compatibility
---------------------------

virtualenv works with the following Python interpreter implementations:

- `CPython <https://www.python.org/>`_ versions 2.7, 3.5, 3.6, 3.7, 3.8, 3.9, 3.10
- `PyPy <https://pypy.org/>`_ 2.7 and 3.5+.

This means virtualenv works on the latest patch version of each of these minor versions. Previous patch versions are
supported on a best effort approach.

CPython is shipped in multiple forms, and each OS repackages it, often applying some customization along the way.
Therefore we cannot say universally that we support all platforms, but rather specify some we test against. In case
of ones not specified here the support is unknown, though likely will work. If you find some cases please open a feature
request on our issue tracker.

Linux
~~~~~
- installations from `python.org <https://www.python.org/downloads/>`_
- Ubuntu 16.04+ (both upstream and `deadsnakes <https://launchpad.net/~deadsnakes/+archive/ubuntu/ppa>`_ builds)
- Fedora
- RHEL and CentOS
- OpenSuse
- Arch Linux

macOS
~~~~~
In case of macOS we support:

- installations from `python.org <https://www.python.org/downloads/>`_
- python versions installed via `brew <https://docs.brew.sh/Homebrew-and-Python>`_ (both older python2.7 and python3)
- Python 3 part of XCode (Python framework - ``/Library/Frameworks/Python3.framework/``)
- Python 2 part of the OS (``/System/Library/Frameworks/Python.framework/Versions/``)

Windows
~~~~~~~
- Installations from `python.org <https://www.python.org/downloads/>`_
- Windows Store Python - note only `version 3.7+ <https://www.microsoft.com/en-us/p/python-38/9mssztt1n39l>`_

Packaging variants
~~~~~~~~~~~~~~~~~~
- Normal variant (file structure as comes from `python.org <https://www.python.org/downloads/>`_).
- We support CPython 2 system installations that do not contain the python files for the standard library if the
  respective compiled files are present (e.g. only ``os.pyc``, not ``os.py``). This can be used by custom systems may
  want to maximize available storage or obfuscate source code by removing ``.py`` files.
