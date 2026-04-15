############
 virtualenv
############

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

.. image:: https://img.shields.io/discord/803025117553754132
    :target: https://discord.gg/pypa
    :alt: Discord

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

``virtualenv`` is a tool to create isolated Python environments. Since Python 3.3, a subset of it has been integrated
into the standard library under the ``venv`` module. For how ``virtualenv`` compares to the stdlib ``venv`` module, see
:doc:`explanation`.

******************
 Quick navigation
******************

**Tutorials** - Learn by doing

- :doc:`tutorial/getting-started` — Create your first virtual environment and learn the basic workflow

**How-to guides** - Solve specific problems

- :doc:`how-to/install` — Install virtualenv on your system
- :doc:`how-to/usage` — Select Python versions, activate environments, configure defaults, and use from Python code

**Reference** - Technical information

- :doc:`reference/compatibility` — Supported Python versions and operating systems
- :doc:`reference/cli` — Command line options and flags
- :doc:`reference/api` — Programmatic Python API reference

**Explanation** - Understand the concepts

- :doc:`explanation` — How virtualenv works under the hood and why it exists

**Extensions**

- :doc:`plugin/index` — Extend virtualenv with custom creators, seeders, and activators

******************
 Related projects
******************

Several tools build on virtualenv to provide higher-level workflows:

- `virtualenvwrapper <https://virtualenvwrapper.readthedocs.io/en/latest/>`_ — Shell wrapper for creating and managing
  multiple virtualenvs
- `pew <https://github.com/berdario/pew>`_ — Python Env Wrapper, a set of commands to manage multiple virtual
  environments
- `tox <https://tox.readthedocs.io/en/latest/>`_ — Automate testing across multiple Python versions
- `nox <https://nox.thea.codes/en/stable/>`_ — Flexible test automation in Python

********************
 External resources
********************

Learn more about virtualenv from these community resources:

- `Corey Schafer's virtualenv tutorial <https://www.youtube.com/watch?v=N5vscPTWKOk>`_ — Video walkthrough for beginners
- `Bernat Gabor's status quo <https://www.youtube.com/watch?v=o1Vue9CWRxU>`_ — Talk about the current state of Python
  packaging
- `Carl Meyer's reverse-engineering <http://pyvideo.org/video/568/reverse-engineering-ian-bicking--39-s-brain--insi>`_ —
  Deep dive into how virtualenv works internally

.. toctree::
    :hidden:
    :caption: Tutorial

    tutorial/getting-started

.. toctree::
    :hidden:
    :caption: How-to guides

    how-to/install
    how-to/usage

.. toctree::
    :hidden:
    :caption: Reference

    reference/compatibility
    reference/cli
    reference/api

.. toctree::
    :hidden:
    :caption: Explanation

    explanation

.. toctree::
    :hidden:
    :caption: Extend

    plugin/index

.. toctree::
    :hidden:
    :caption: Project

    development
    changelog
