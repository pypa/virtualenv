Differences with venv
=====================

- ``venv`` is bundled with Python itself (starting from 3.3+), ``virtualenv``
  is a third party package. This allows for ``virtualenv`` to have greater
  flexibility when dealing with several Python versions.
- ``virtualenv`` allows further :doc:`extendibility <extend>` to override default
  functionality through a plugin system.
- ``virtualenv`` can create virtual environments through its interpreter discovery
  technique from arbitrary Python locations, they do not be installed or be on the
  ``PATH``.
- ``venv`` can only create virtual environments for the Python version it is
  installed with, ``virtualenv`` supports both Python 2 and 3 and also other flavours
  like ``CPython`` and ``PyPy``.
- ``virtualenv`` has a rich programmatic API (describe virtual environments without
  creating them).
- ``virtualenv`` has better support across different platforms and shells.
