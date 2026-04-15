#########
 Plugins
#########

virtualenv can be extended via plugins using Python entry points. Plugins are automatically discovered from the Python
environment where virtualenv is installed, allowing you to customize how virtual environments are created, seeded, and
activated.

******************
 Extension points
******************

virtualenv provides four extension points through entry point groups:

``virtualenv.discovery``
    Python interpreter discovery plugins. These plugins locate and identify Python interpreters that will be used as the
    base for creating virtual environments.

``virtualenv.create``
    Virtual environment creator plugins. These plugins handle the actual creation of the virtual environment structure,
    including copying or symlinking the Python interpreter and standard library.

``virtualenv.seed``
    Seed package installer plugins. These plugins install initial packages (like pip, setuptools, wheel) into newly
    created virtual environments.

``virtualenv.activate``
    Shell activation script plugins. These plugins generate shell-specific activation scripts that modify the
    environment to use the virtual environment.

All extension points follow a common pattern: virtualenv discovers registered entry points, builds CLI options from
them, and executes the selected implementations during environment creation.

.. toctree::

    tutorial
    how-to
    api
    architecture
