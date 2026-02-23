################
 Use virtualenv
################

*************************
 Select a Python version
*************************

By default, virtualenv uses the same Python version it runs under. Override this with ``--python`` or ``-p``.

Using version specifiers
========================

Specify a Python version by name or version number:

.. code-block:: console

    $ virtualenv -p python3.8 venv
    $ virtualenv -p 3.10 venv
    $ virtualenv -p pypy3 venv

Using PEP 440 specifiers
========================

Use `PEP 440 <https://peps.python.org/pep-0440/#version-specifiers>`_ version specifiers to match Python versions:

.. code-block:: console

    $ virtualenv --python ">=3.12" venv
    $ virtualenv --python "~=3.11.0" venv
    $ virtualenv --python "cpython>=3.10" venv

- ``>=3.12`` -- any Python 3.12 or later.
- ``~=3.11.0`` -- compatible release, equivalent to ``>=3.11.0, <3.12.0`` (any 3.11.x patch).
- ``cpython>=3.10`` -- restrict to CPython implementation, 3.10 or later.

Using free-threading Python
===========================

Create an environment with `free-threading Python <https://docs.python.org/3/howto/free-threading-python.html>`_:

.. code-block:: console

    $ virtualenv -p 3.13t venv

Targeting a specific CPU architecture
=====================================

On machines that support multiple architectures — such as Apple Silicon (arm64 + x86_64 via Rosetta) or Windows on ARM —
you can request a specific CPU architecture by appending it to the spec string:

.. code-block:: console

    $ virtualenv -p cpython3.12-64-arm64 venv
    $ virtualenv -p 3.11-64-x86_64 venv

Cross-platform aliases are normalized automatically, so ``amd64`` and ``x86_64`` are treated as equivalent, as are
``aarch64`` and ``arm64``. If omitted, any architecture matches (preserving existing behavior).

Using absolute paths
====================

Specify the full path to a Python interpreter:

.. code-block:: console

    $ virtualenv -p /usr/bin/python3.9 venv

Using ``--try-first-with``
==========================

Use ``--try-first-with`` to provide a hint about which Python to check first. Unlike ``--python``, this is a hint rather
than a rule. The interpreter at this path is checked first, but only used if it matches the ``--python`` constraint.

.. code-block:: console

    $ virtualenv --python ">=3.10" --try-first-with /usr/bin/python3.9 venv

In this example, /usr/bin/python3.9 is checked first but rejected because it does not satisfy the >=3.10 constraint.

********************************
 Activate a virtual environment
********************************

Activate the environment to modify your shell's PATH and environment variables.

.. tab:: Bash/Zsh

    .. code-block:: console

       $ source venv/bin/activate

.. tab:: Fish

    .. code-block:: console

       $ source venv/bin/activate.fish

.. tab:: PowerShell

    .. code-block:: console

       PS> .\venv\Scripts\Activate.ps1

    .. note::

       If you encounter an execution policy error, run ``Set-ExecutionPolicy RemoteSigned`` to allow local scripts.

.. tab:: CMD

    .. code-block:: console

       > .\venv\Scripts\activate.bat

.. tab:: Nushell

    .. code-block:: console

       $ overlay use venv/bin/activate.nu

Deactivate the environment
==========================

Exit the virtual environment:

.. code-block:: console

    $ deactivate

Use without activation
======================

Use the environment without activating it by calling executables with their full paths:

.. code-block:: console

    $ venv/bin/python script.py
    $ venv/bin/pip install package

Customize prompt
================

Set a custom prompt prefix:

.. code-block:: console

    $ virtualenv --prompt myproject venv

Disable the prompt modification by setting the ``VIRTUAL_ENV_DISABLE_PROMPT`` environment variable.

Access the prompt string via the ``VIRTUAL_ENV_PROMPT`` environment variable.

Programmatic activation
=======================

Activate the environment from within a running Python process using ``activate_this.py``. This modifies ``sys.path`` and
environment variables in the current process so that subsequent imports resolve from the virtual environment.

.. code-block:: python

    import runpy

    runpy.run_path("venv/bin/activate_this.py")

A common use case is web applications served by a system-wide WSGI server (such as mod_wsgi or uWSGI) that need to load
packages from a virtual environment:

.. code-block:: python

    import runpy
    from pathlib import Path

    runpy.run_path(str(Path("/var/www/myapp/venv/bin/activate_this.py")))

    from myapp import create_app  # noqa: E402

    application = create_app()

********************
 Configure defaults
********************

Use a configuration file to set default options for virtualenv.

Configuration file location
===========================

The configuration file is named ``virtualenv.ini`` and located in the platformdirs app config directory. Run
``virtualenv --help`` to see the exact location for your system.

Override the location with the ``VIRTUALENV_CONFIG_FILE`` environment variable.

Configuration format
====================

Derive configuration keys from command-line options by stripping leading ``-`` and replacing remaining ``-`` with ``_``:

.. code-block:: ini

    [virtualenv]
    python = /opt/python-3.8/bin/python

Multi-value options
===================

Specify multiple values on separate lines:

.. code-block:: ini

    [virtualenv]
    extra_search_dir =
        /path/to/dists
        /path/to/other/dists

Environment variables
=====================

Set options using environment variables with the ``VIRTUALENV_`` prefix and uppercase key names:

.. code-block:: console

    $ export VIRTUALENV_PYTHON=/opt/python-3.8/bin/python

For multi-value options, separate values with commas or newlines.

Override app-data location
==========================

Set the ``VIRTUALENV_OVERRIDE_APP_DATA`` environment variable to override the default app-data cache directory location.

Configuration priority
======================

Options are resolved in this order (highest to lowest priority):

.. mermaid::

    block-beta
        columns 1
        A["Command-line arguments (highest)"]
        B["Environment variables"]
        C["Configuration file"]
        D["Default values (lowest)"]

        style A fill:#16a34a,stroke:#15803d,color:#fff
        style B fill:#2563eb,stroke:#1d4ed8,color:#fff
        style C fill:#d97706,stroke:#b45309,color:#fff
        style D fill:#6366f1,stroke:#4f46e5,color:#fff

***********************
 Control seed packages
***********************

Upgrade embedded wheels
=======================

Update the embedded wheel files to the latest versions:

.. code-block:: console

    $ virtualenv --upgrade-embed-wheels

Provide custom wheels
=====================

Use custom wheel files from a local directory:

.. code-block:: console

    $ virtualenv --extra-search-dir /path/to/wheels venv

Download latest from PyPI
=========================

Download the latest versions of seed packages from PyPI:

.. code-block:: console

    $ virtualenv --download venv

Disable periodic updates
========================

Disable automatic periodic updates of seed packages:

.. code-block:: console

    $ virtualenv --no-periodic-update venv

For distribution maintainers
============================

Patch the ``virtualenv.seed.wheels.embed`` module and set ``PERIODIC_UPDATE_ON_BY_DEFAULT`` to ``False`` to disable
periodic updates by default. See :doc:`../explanation` for implementation details.

**********************
 Use from Python code
**********************

Call virtualenv from Python code using the ``cli_run`` function:

.. code-block:: python

    from virtualenv import cli_run

    cli_run(["venv"])

Pass options as list elements:

.. code-block:: python

    cli_run(["-p", "python3.8", "--without-pip", "myenv"])

Use the returned session object to access environment details:

.. code-block:: python

    result = cli_run(["venv"])
    print(result.creator.dest)  # path to created environment
    print(result.creator.exe)  # path to python executable

Use ``session_via_cli`` to describe the environment without creating it:

.. code-block:: python

    from virtualenv import session_via_cli

    session = session_via_cli(["venv"])
    # inspect session.creator, session.seeder, session.activators

See :doc:`../reference/api` for complete API documentation.
