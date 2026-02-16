.. _compatibility-requirements:

###############
 Compatibility
###############

**********************************
 Supported Python implementations
**********************************

``virtualenv`` works with the following Python interpreter implementations. Only the latest patch version of each minor
version is fully supported; previous patch versions work on a best effort basis.

CPython
=======

``3.14 >= python_version >= 3.8``

PyPy
====

``3.11 >= python_version >= 3.8``

GraalPy
=======

``24.1`` and later (Linux and macOS only).

****************
 Support policy
****************

- **New versions** are added close to their release date, typically during the beta phase.
- **Old versions** are dropped 18 months after `CPython EOL <https://devguide.python.org/versions/>`_, giving users
  plenty of time to migrate.

**************************
 Version support timeline
**************************

Major version support changes:

- **20.27.0** (2024-10-17): dropped support for running under Python 3.7 and earlier.
- **20.22.0** (2023-04-19): dropped support for creating environments for Python 3.6 and earlier.
- **20.18.0** (2023-02-06): dropped support for running under Python 3.6 and earlier.

*****************************
 Supported operating systems
*****************************

CPython is shipped in multiple forms, and each OS repackages it, often applying some customization. The platforms listed
below are tested. Unlisted platforms may work but are not explicitly supported. If you encounter issues on unlisted
platforms, please open a feature request.

Cross-platform
==============

These Python distributions work on Linux, macOS, and Windows:

- Installations from `python.org <https://www.python.org/downloads/>`_
- `python-build-standalone <https://github.com/astral-sh/python-build-standalone>`_ builds (used by `uv
  <https://docs.astral.sh/uv/>`_ and `mise <https://mise.jdx.dev/>`_)

Linux
=====

- Ubuntu 16.04 and later (both upstream and `deadsnakes <https://launchpad.net/~deadsnakes/+archive/ubuntu/ppa>`_
  builds)
- Fedora
- RHEL and CentOS
- OpenSuse
- Arch Linux

macOS
=====

- Python versions installed via `Homebrew <https://docs.brew.sh/Homebrew-and-Python>`_ (works, but `not recommended
  <https://justinmayer.com/posts/homebrew-python-is-not-for-you/>`_ -- Homebrew may upgrade or remove Python versions
  without warning, breaking existing virtual environments)
- Python 3 part of XCode (Python framework builds at ``/Library/Frameworks/Python3.framework/``)

.. note::

    Framework builds do not support copy-based virtual environments. Use symlink or hardlink creation methods instead.

Windows
=======

- `Windows Store <https://apps.microsoft.com/search?query=python>`_ Python 3.8 and later
