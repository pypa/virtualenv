######################
 Plugin API reference
######################

This page documents the interfaces that plugins must implement.

***********
 Discovery
***********

Discovery plugins locate Python interpreters for creating virtual environments.

.. currentmodule:: virtualenv.discovery.discover

.. autoclass:: Discover
    :undoc-members:
    :members:

PythonInfo
==========

Discovery plugins return a ``PythonInfo`` object describing the located interpreter.

.. currentmodule:: virtualenv.discovery.py_info

.. autoclass:: PythonInfo
    :undoc-members:
    :members:

**********
 App data
**********

The application data interface used by plugins for caching.

.. currentmodule:: virtualenv.app_data.base

.. autoclass:: AppData
    :members:

**********
 Creators
**********

Creator plugins build the virtual environment directory structure and install the Python interpreter.

.. currentmodule:: virtualenv.create.creator

.. autoclass:: CreatorMeta
    :members:

.. autoclass:: Creator
    :undoc-members:
    :members:
    :exclude-members: run, set_pyenv_cfg, debug_script, validate_dest, debug

*********
 Seeders
*********

Seeder plugins install initial packages (like pip, setuptools, wheel) into the virtual environment.

.. currentmodule:: virtualenv.seed.seeder

.. autoclass:: Seeder
    :undoc-members:
    :members:

************
 Activators
************

Activator plugins generate shell-specific activation scripts.

.. currentmodule:: virtualenv.activation.activator

.. autoclass:: Activator
    :undoc-members:
    :members:
