####################
 Install virtualenv
####################

virtualenv is a command-line tool, so it should be installed in an isolated environment rather than into your system
Python. Pick the method that fits your setup:

- `uv <https://docs.astral.sh/uv/>`_ -- fast, modern Python package manager. Use this if you already have ``uv`` or are
  starting fresh.
- `pipx <https://pipx.pypa.io/stable/>`_ -- installs Python CLI tools in isolated environments. Use this if you already
  have ``pipx`` set up.
- `pip <https://pip.pypa.io/stable/>`_ -- the standard Python package installer. Use ``--user`` to avoid modifying
  system packages. May not work on distributions with externally-managed Python environments.
- `zipapp <https://docs.python.org/3/library/zipapp.html>`_ -- a self-contained executable requiring no installation.
  Use this in CI or environments where you cannot install packages.

.. mermaid::

    flowchart TD
        A{Can you install packages?} -->|Yes| B{Have uv?}
        A -->|No| Z[zipapp]
        B -->|Yes| U[uv tool install]
        B -->|No| C{Have pipx?}
        C -->|Yes| P[pipx install]
        C -->|No| D[pip install --user]

        style A fill:#d97706,stroke:#b45309,color:#fff
        style B fill:#d97706,stroke:#b45309,color:#fff
        style C fill:#d97706,stroke:#b45309,color:#fff
        style U fill:#16a34a,stroke:#15803d,color:#fff
        style P fill:#16a34a,stroke:#15803d,color:#fff
        style D fill:#7c3aed,stroke:#6d28d9,color:#fff
        style Z fill:#7c3aed,stroke:#6d28d9,color:#fff

.. tab:: uv

    Install virtualenv as a `uv tool <https://docs.astral.sh/uv/concepts/tools/>`_:

    .. code-block:: console

       $ uv tool install virtualenv

    Install the development version:

    .. code-block:: console

       $ uv tool install git+https://github.com/pypa/virtualenv.git@main

.. tab:: pipx

    Install virtualenv using `pipx <https://pipx.pypa.io/stable/>`_:

    .. code-block:: console

       $ pipx install virtualenv

    Install the development version:

    .. code-block:: console

       $ pipx install git+https://github.com/pypa/virtualenv.git@main

.. tab:: pip

    Install virtualenv using `pip <https://pip.pypa.io/stable/>`_:

    .. code-block:: console

       $ python -m pip install --user virtualenv

    Install the development version:

    .. code-block:: console

       $ python -m pip install git+https://github.com/pypa/virtualenv.git@main

    .. warning::

       Some Linux distributions use system-managed Python environments. If you encounter errors about externally-managed
       environments, use ``uv tool`` or ``pipx`` instead.

.. tab:: zipapp

    Download the zipapp file and run it directly:

    .. code-block:: console

       $ python virtualenv.pyz --help

    Download the latest version from https://bootstrap.pypa.io/virtualenv.pyz or a specific version from
    ``https://bootstrap.pypa.io/virtualenv/x.y/virtualenv.pyz``.

*********************
 Verify installation
*********************

Check the installed version:

.. code-block:: console

    $ virtualenv --version

See :doc:`../reference/compatibility` for supported Python versions.
