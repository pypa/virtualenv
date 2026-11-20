##############
 Command line
##############

``virtualenv`` is primarily a command line application. All options have sensible defaults, and there is one required
argument: the name or path of the virtual environment to create.

Choose an environment path whose first ``%`` does not start ``%func`` or ``%builtin``. On POSIX and in Git for Windows,
`dash treats those spellings as PATH options
<https://kernel.googlesource.com/pub/scm/utils/dash/dash/+/a29e9a1738a4e7040211842f3f3d90e172fa58ce/src/exec.c#419>`_
during command lookup. Other percent signs are allowed.

See :doc:`../how-to/usage` for how to select Python versions, configure defaults, and use environment variables.

**********************
 Command line options
**********************

:command:`virtualenv [OPTIONS]`

.. table_cli::
    :module: virtualenv.run
    :func: build_parser_only
