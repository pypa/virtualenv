Extend functionality
====================

``virtualenv`` allows one to extend the builtin functionality via a plugin system. To add a plugin you need to:

- write a python file containing the plugin code which follows our expected interface,
- package it as a python library,
- install it alongside the virtual environment.

.. warning::

   The public API of some of these components is still to be finalized, consider the current interface a beta one
   until we get some feedback on how well we planned ahead. We expect to do this by end of Q3 2020. Consider the class
   interface explained below as initial draft proposal. We reserve the right to change the API until then, however such
   changes will be communicated in a timely fashion, and you'll have time to migrate. Thank you for your understanding.

Python discovery
----------------

The python discovery mechanism is a component that needs to answer the following answer: based on some type of user
input give me a Python interpreter on the machine that matches that. The builtin interpreter tries to discover
an installed Python interpreter (based on PEP-515 and ``PATH`` discovery) on the users machine where the user input is a
python specification. An alternative such discovery mechanism for example would be to use the popular
`pyenv <https://github.com/pyenv/pyenv>`_ project to discover, and if not present install the requested Python
interpreter. Python discovery mechanisms must be registered under key ``virtualenv.discovery``, and the plugin must
implement :class:`virtualenv.discovery.discover.Discover`:

.. code-block:: ini

   virtualenv.discovery =
        pyenv = virtualenv_pyenv.discovery:PyEnvDiscovery


.. currentmodule:: virtualenv.discovery.discover

.. autoclass:: Discover
    :undoc-members:
    :members:


Creators
--------
Creators are what actually perform the creation of a virtual environment. The builtin virtual environment creators
all achieve this by referencing a global install; but would be just as valid for a creator to install a brand new
entire python under the target path; or one could add additional creators that can create virtual environments for other
python implementations, such as IronPython. They must be registered under and entry point with key
``virtualenv.discovery`` , and the class must implement :class:`virtualenv.create.creator.Creator`:

.. code-block:: ini

   virtualenv.create =
        cpython3-posix = virtualenv.create.via_global_ref.builtin.cpython.cpython3:CPython3Posix

.. currentmodule:: virtualenv.create.creator

.. autoclass:: Creator
    :undoc-members:
    :members:
    :exclude-members: run, set_pyenv_cfg, debug_script, debug_script, validate_dest, debug


Seed mechanism
--------------

Seeders are what given a virtual environment will install somehow some seed packages into it. They must be registered
under and entry point with key ``virtualenv.seed`` , and the class must implement
:class:`virtualenv.seed.seeder.Seeder`:

.. code-block:: ini

   virtualenv.seed =
        db = virtualenv.seed.fromDb:InstallFromDb

.. currentmodule:: virtualenv.seed.seeder

.. autoclass:: Seeder
    :undoc-members:
    :members:

Activation scripts
------------------
If you want add an activator for a new shell you can do this by implementing a new activator. They must be registered
under and entry point with key ``virtualenv.activate`` , and the class must implement
:class:`virtualenv.activation.activator.Activator`:

.. code-block:: ini

   virtualenv.activate =
        bash = virtualenv.activation.bash:BashActivator

.. currentmodule:: virtualenv.activation.activator

.. autoclass:: Activator
    :undoc-members:
    :members:
