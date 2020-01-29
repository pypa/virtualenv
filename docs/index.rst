Virtualenv
==========

.. image:: https://badge.fury.io/py/virtualenv.svg
  :target: https://badge.fury.io/py/virtualenv
  :alt: Latest version on PyPI
.. image:: https://img.shields.io/pypi/pyversions/virtualenv.svg
  :target: https://pypi.org/project/virtualenv/
  :alt: Supported Python versions
.. image:: https://readthedocs.org/projects/virtualenv/badge/?version=latest&style=flat-square
  :target: https://virtualenv.pypa.io
  :alt: Documentation status
.. image:: https://img.shields.io/pypi/l/virtualenv?style=flat-square
  :target: https://github.com/pypa/virtualenv/pulls
  :alt: License
.. image:: https://img.shields.io/github/issues-pr/pypa/virtualenv?style=flat-square
  :target: https://opensource.org/licenses/MIT
  :alt: Open issues
.. image:: https://img.shields.io/github/issues/pypa/virtualenv?style=flat-square
  :target: https://github.com/pypa/virtualenv/pulls
  :alt: Open pull requests
.. image:: https://img.shields.io/pypi/dm/virtualenv?style=flat-square
  :target: https://github.com/pypa/virtualenv
  :alt: Source code
.. image:: https://img.shields.io/github/stars/pypa/virtualenv?style=flat-square
  :target: https://pypistats.org/packages/virtualenv
  :alt: Package popularity

``virtualenv`` is a tool to create isolated Python environments. Since Python ``3.3``, a subset of it has been
integrated into the standard library under the  `venv module <https://docs.python.org/3/library/venv.html>`_.
The ``venv`` module does not offer all features of this library:

- is slower (by not having the ``app-data`` seed method),
- is not as extensible,
- cannot create virtual environments for arbitrarily installed python versions (and automatically discover these),
- is not upgrade-able via `pip <https://pip.pypa.io/en/stable/installing/>`_,
- does not have as rich programmatic API (describe virtual environments without creating them),
- etc.

The basic problem being addressed is one of dependencies and versions, and indirectly permissions.
Imagine you have an application that needs version ``1`` of ``LibFoo``, but another application requires version
``2``. How can you use both these libraries?  If you install everything into your host python (e.g. ``python3.8``)
it's easy to end up in a situation where two packages have conflicting requirements. Or more generally,
what if you want to install an application *and leave it be*?  If an application works, any change in its libraries or
the versions of those libraries can break the application. Also, what if you can't install packages into the global
``site-packages`` directory, due to not having permissions to change the host python environment?

In all these cases, ``virtualenv`` can help you. It creates an environment that has its own installation directories,
that doesn't share libraries with other virtualenv environments (and optionally doesn't access the globally installed
libraries either).

Useful links
------------

**Related projects, abstsractions on top of it**

* :pypi:`virtualenvwrapper` is a useful set of scripts to make your workflow with many virtualenv even easier
* :pypi:`pew` is another wrapper for virtualenv that makes use of a different activation technique.
* :pypi:`tox` - integrates setting up and running tests within virtual environments driven by a ``tox.ini``
  configuration file
* :pypi:`nox` - integrates setting up and running tests within virtual environments driven by a ``nox.py``
  python file

**Tutorials**

* `Corey Schafer tutorial <https://www.youtube.com/watch?v=N5vscPTWKOk>`_ on how to use it.
* `Using virtualenv with mod_wsgi <http://code.google.com/p/modwsgi/wiki/VirtualEnvironments>`_.

**Presenting how the package works from within**

* `Bernat Gabor: status quo of virtual environments <https://www.youtube.com/watch?v=o1Vue9CWRxU>`_.
* `Carl Meyer: Reverse-engineering Ian Bicking's brain: inside pip and virtualenv
  <http://pyvideo.org/video/568/reverse-engineering-ian-bicking--39-s-brain--insi>`_.

.. comment: split here

.. toctree::
   :hidden:

   installation
   user_guide
   cli_interface
   extend
   development
   changes
