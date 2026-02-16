##############
 Command line
##############

``virtualenv`` is primarily a command line application. All options have sensible defaults, and there is one required
argument: the name or path of the virtual environment to create.

See :doc:`../how-to/usage` for how to select Python versions, configure defaults, and use environment variables.

**********************
 Command line options
**********************

:command:`virtualenv [OPTIONS]`

.. table_cli::
    :module: virtualenv.run
    :func: build_parser_only
