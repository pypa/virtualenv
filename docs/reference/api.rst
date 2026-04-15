.. _programmatic_api:

########
 Python
########

The primary interface to ``virtualenv`` is the command line application. However, it can also be used programmatically
via the ``virtualenv.cli_run`` function and the ``Session`` class.

See :doc:`../how-to/usage` for usage examples.

*******************
 virtualenv module
*******************

.. automodule:: virtualenv
    :members:

***************
 Session class
***************

The ``Session`` class represents a virtualenv creation session and provides access to the created environment's
properties.

.. currentmodule:: virtualenv.run.session

.. autoclass:: Session
    :members:

*******************
 VirtualEnvOptions
*******************

Options namespace passed to plugin constructors, populated from the CLI, environment variables, and configuration files.

.. currentmodule:: virtualenv.config.cli.parser

.. autoclass:: VirtualEnvOptions
    :members:
