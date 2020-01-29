CLI interface
=============

.. _cli_flags:

cli flags
~~~~~~~~~

``virtualenv`` is primarily a command line interface application. It's mainly aimed to be used from a command line, as
such you'll need to to have a shell to run it. Then you can type in ``virtualenv`` (name of the application) followed by
flags that control its behaviour. All options do have a sensible default, so if you pass no options you'll get a
virtual environment in the current working directories ``venv`` folder. The Default values for the command line
options can be modified either via the :ref:`conf_file` or :ref:`env_vars`. Environment variables takes priority over
the configuration file values (the ``--help`` will show if a default comes from the environment variable as the help
message will end in this case either with ``via env var`` or ``via config file``).

Below you can see the options you can pass in, together with its default value, and a short description of what it does:

:command:`virtualenv [OPTIONS]`

.. table_cli::
   :module: virtualenv.run
   :func: build_parser

Defaults
~~~~~~~~

.. _conf_file:

Configuration file
^^^^^^^^^^^^^^^^^^

virtualenv looks for a standard ini config file. The exact place depends on the operating system you're using, as
determined by :pypi:`appdirs` application data definition. The config file location is printed as epilog for the CLI
tools help message.

The keys of the settings are derived from the long command line option, e.g. the option :option:`--python <python>`
would look like this:

.. code-block:: ini

  [virtualenv]
  python = /opt/python-3.3/bin/python

Appending options like :option:`extra-search-dir` can be written on multiple lines:

.. code-block:: ini

  [virtualenv]
  extra-search-dir =
      /path/to/dists
      /path/to/other/dists

.. _env_vars:

Environment Variables
^^^^^^^^^^^^^^^^^^^^^

Each command line option is automatically used to look for environment variables with the name format
``VIRTUALENV_<UPPER_NAME>``. That means the name of the command line options are capitalized and have dashes (``'-'``)
replaced with underscores (``'_'``).

For example, to automatically use a custom Python binary instead of the one virtualenv is run with you can also set an
environment variable:

.. code-block:: console

   env VIRTUALENV_PYTHON=/opt/python-3.8/bin/python virtualenv

This also works for appending command line options, like :option:`extra-search-dir`. Just pass a literal newline
between the passed values, e.g.:

.. code-block:: console

  env VIRTUALENV_EXTRA_SEARCH_DIR="/path/to/dists\n/path/to/other/dists" virtualenv

is the same as calling:

.. code-block:: console

   virtualenv --extra-search-dir=/path/to/dists --extra-search-dir=/path/to/other/dists
