Installation
============

via pipx
--------

:pypi:`virtualenv` is a CLI tool that needs a Python interpreter to run. If you already have a ``Python 3.5+``
interpreter the best is to use :pypi:`pipx` to install virtualenv into an isolated environment. This has the added
benefit that later you'll be able to upgrade virtualenv without affecting other parts of the system.

.. code-block:: console

    $ pipx install virtualenv
    $ virtualenv --help

via pip
-------
Alternatively you can install it within the global Python interpreter itself (perhaps as a user package via the
``--user`` flag). Be cautious if you are using a python install that is managed by your operating system or
another package manager. ``pip`` might not coordinate with those tools, and may leave your system in an
inconsistent state.

.. code-block:: console

    $ python -m pip --user install virtualenv
    $ python -m virtualenv --help

via zipapp
~~~~~~~~~~

You can use virtualenv without installing it too. We publish a Python
`zipapp <https://docs.python.org/3/library/zipapp.html>`_, you can just download this from
`https://bootstrap.pypa.io/get-virtualenv.pyz <https://bootstrap.pypa.io/get-virtualenv.pyz>`_ and invoke this package
with a python interpreter:

.. code-block:: console

    $ python virtualenv.pyz --help

.. _compatibility-requirements:

Python and OS Compatibility
---------------------------

pip works with the following Python interpreter implementations:

- `CPython <https://www.python.org/>`_ versions 2.7, 3.4, 3.5, 3.6, 3.7, 3.8
- `PyPy <https://pypy.org/>`_ 2.7 and 3.4+.

This means pip works on the latest patch version of each of these minor versions. Previous patch versions are supported
on a best effort approach.

pip works on the following platforms:

- Unix/Linux,
- macOS,
- Windows.


In Windows, run the ``pip`` provided by your Python installation to install ``virtualenv``.
