virtualenv - Isolated Python Environments
=========================================

.. image:: https://img.shields.io/pypi/v/virtualenv?style=flat-square
  :target: https://pypi.org/project/virtualenv/#history
  :alt: Latest version on PyPI
.. image:: https://img.shields.io/pypi/implementation/virtualenv?style=flat-square
  :alt: PyPI - Implementation
.. image:: https://img.shields.io/pypi/pyversions/virtualenv?style=flat-square
  :alt: PyPI - Python Version
.. image:: https://readthedocs.org/projects/virtualenv/badge/?version=latest&style=flat-square
  :target: https://virtualenv.pypa.io
  :alt: Documentation status
.. image:: https://img.shields.io/gitter/room/pypa/virtualenv?color=FF004F&style=flat-square
  :target: https://gitter.im/pypa/virtualenv
  :alt: Gitter
.. image:: https://img.shields.io/pypi/dm/virtualenv?style=flat-square
  :target: https://pypistats.org/packages/virtualenv
  :alt: PyPI - Downloads
.. image:: https://img.shields.io/pypi/l/virtualenv?style=flat-square
  :target: https://opensource.org/licenses/MIT
  :alt: PyPI - License
.. image:: https://img.shields.io/github/issues/pypa/virtualenv?style=flat-square
  :target: https://github.com/pypa/virtualenv/issues
  :alt: Open issues
.. image:: https://img.shields.io/github/issues-pr/pypa/virtualenv?style=flat-square
  :target: https://github.com/pypa/virtualenv/pulls
  :alt: Open pull requests
.. image:: https://img.shields.io/github/stars/pypa/virtualenv?style=flat-square
  :target: https://pypistats.org/packages/virtualenv
  :alt: Package popularity

``virtualenv`` is a tool to create isolated Python environments with its own copy of
a working Python environment that is isolated from the rest of the system.

.. note::
  Since Python ``3.3``, a subset of it has been integrated into the standard library under the `venv module <https://docs.Python.org/3/library/venv.html>`_. The
  ``venv`` module does not offer all features of this library. See the :doc:`differences <differences_with_venv>` betwwen virtualenv and venv.

The need for isolation of Python environments comes when there are two Python
libraries with their own set of dependencies, Python versions and permissions.
Python applications will often use external libraries that are not part of the standard Python
library. The applications will often require a specific version  of that library where a particular
bug has been fixed. Imagine you have an application that needs version ``1.2.3`` of ``foo``,
but another application requires version ``2.3.4``. Installing one version of the library would
make the other application unable to run. So, If you install everything into your system Python
it's easy to end up in a situation where two applications have conflicting requirements.

Or more generally, what if you want to install an application *and leave it be*? If an application works, any change
in its libraries or the versions of those libraries can break the application. Also, what if you can't install packages
into the global ``site-packages`` directory, due to not having permissions to change the system Python environment?

In all these cases, ``virtualenv`` can help you. It creates an environment that has its own installation directories,
that doesn't share libraries with other virtualenv environments (and optionally doesn't access the globally installed
libraries either).

.. _differences: differences_with_venv

.. comment: split here

.. toctree::
   :hidden:

   installation
   user_guide
   cli_interface
   extend
   development
   changelog
   differences_with_venv
   useful_links
