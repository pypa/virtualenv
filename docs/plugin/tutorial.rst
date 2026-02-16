###################
 Your first plugin
###################

This tutorial walks through creating a simple discovery plugin that locates Python interpreters managed by pyenv.

******************************
 Create the package structure
******************************

Set up a new Python package with the following structure:

.. code-block:: text

    virtualenv-pyenv/
    ├── pyproject.toml
    └── src/
        └── virtualenv_pyenv/
            └── __init__.py

***************************
 Configure the entry point
***************************

In ``pyproject.toml``, declare your plugin as an entry point under the ``virtualenv.discovery`` group:

.. code-block:: toml

    [project]
    name = "virtualenv-pyenv"
    version = "0.1.0"
    dependencies = ["virtualenv>=20"]

    [project.entry-points."virtualenv.discovery"]
    pyenv = "virtualenv_pyenv:PyEnvDiscovery"

    [build-system]
    requires = ["setuptools>=61"]
    build-backend = "setuptools.build_meta"

**********************
 Implement the plugin
**********************

In ``src/virtualenv_pyenv/__init__.py``, implement the discovery plugin by subclassing ``Discover``:

.. code-block:: python

    from __future__ import annotations

    import subprocess
    from pathlib import Path

    from virtualenv.discovery.discover import Discover
    from virtualenv.discovery.py_info import PythonInfo


    class PyEnvDiscovery(Discover):
        def __init__(self, options):
            super().__init__(options)
            self.python_spec = options.python if options.python else "python"

        @classmethod
        def add_parser_arguments(cls, parser):
            parser.add_argument(
                "--python",
                dest="python",
                metavar="py",
                type=str,
                default=None,
                help="pyenv Python version to use (e.g., 3.11.0)",
            )

        def run(self):
            try:
                result = subprocess.run(
                    ["pyenv", "which", "python"],
                    capture_output=True,
                    text=True,
                    check=True,
                )
                python_path = Path(result.stdout.strip())
                return PythonInfo.from_exe(str(python_path))
            except (subprocess.CalledProcessError, FileNotFoundError) as e:
                raise RuntimeError(f"Failed to locate pyenv Python: {e}")

********************
 Install the plugin
********************

Install your plugin in development mode alongside virtualenv:

.. code-block:: console

    $ pip install -e virtualenv-pyenv/

*******************
 Verify the plugin
*******************

Check that virtualenv recognizes your plugin by running:

.. code-block:: console

    $ virtualenv --discovery help

The output should list ``pyenv`` as an available discovery mechanism. You can now use it:

.. code-block:: console

    $ virtualenv --discovery=pyenv myenv
    created virtual environment CPython3.11.0.final.0-64 in 234ms
      creator CPython3Posix(dest=/path/to/myenv, clear=False, no_vcs_ignore=False, global=False)
      seeder FromAppData(download=False, pip=bundle, setuptools=bundle, wheel=bundle, via=copy, app_data_dir=/path)
        added seed packages: pip==23.0, setuptools==65.5.0, wheel==0.38.4
      activators BashActivator,CShellActivator,FishActivator,NushellActivator,PowerShellActivator,PythonActivator
