CLI interface
=============

.. _cli_flags:

CLI flags
~~~~~~~~~

``virtualenv`` is primarily a command line application.

It modifies the environment variables in a shell to create an isolated Python environment, so you'll need to have a
shell to run it. You can type in ``virtualenv`` (name of the application) followed by flags that control its
behaviour. All options have sensible defaults, and there's one required argument: then name/path of the virtual
environment to create. The default values for the command line options can be overridden via the
:ref:`conf_file` or :ref:`env_vars`. Environment variables takes priority over the configuration file values
(``--help`` will show if a default comes from the environment variable as the help message will end in this case
with environment variables or the configuration file).

The options that can be passed to virtualenv, along with their default values and a short description are listed below.

:command:`virtualenv [OPTIONS]`

.. table_cli::
   :module: virtualenv.run
   :func: build_parser_only

Defaults
~~~~~~~~

.. _conf_file:

Configuration file
^^^^^^^^^^^^^^^^^^

virtualenv looks for a standard ini configuration file. The exact location depends on the operating system you're using,
as determined by :pypi:`appdirs` application configuration definition. The configuration file location is printed as at
the end of the output when ``--help`` is passed.

The keys of the settings are derived from the command line option (left strip the ``-`` characters, and replace ``-``
with ``_``). Where multiple flags are available first found wins (where order is as it shows up under the ``--help``).

For example, :option:`--python <python>` would be specified as:

.. code-block:: ini

  [virtualenv]
  python = /opt/python-3.8/bin/python

Options that take multiple values, like :option:`extra-search-dir` can be specified as:

.. code-block:: ini

  [virtualenv]
  extra_search_dir =
      /path/to/dists
      /path/to/other/dists

.. _env_vars:

Environment Variables
^^^^^^^^^^^^^^^^^^^^^

Default values may be also specified via environment variables. The keys of the settings are derived from the
command line option (left strip the ``-`` characters, and replace ``-`` with ``_``, finally capitalize the name). Where
multiple flags are available first found wins (where order is as it shows up under the ``--help``).

For example, to use a custom Python binary, instead of the one virtualenv is run with, you can set the environment
variable ``VIRTUALENV_PYTHON`` like:

.. code-block:: console

   env VIRTUALENV_PYTHON=/opt/python-3.8/bin/python virtualenv

Where the option accepts multiple values, for example for :option:`python` or
:option:`extra-search-dir`, the values can be separated either by literal
newlines or commas. Newlines and commas can not be mixed and if both are
present only the newline is used for separating values. Examples for multiple
values:


.. code-block:: console

   env VIRTUALENV_PYTHON=/opt/python-3.8/bin/python,python3.8 virtualenv
   env VIRTUALENV_EXTRA_SEARCH_DIR=/path/to/dists\n/path/to/other/dists virtualenv

The equivalent CLI-flags based invocation for the above examples would be:

.. code-block:: console

   virtualenv --python=/opt/python-3.8/bin/python --python=python3.8
   virtualenv --extra-search-dir=/path/to/dists --extra-search-dir=/path/to/other/dists
