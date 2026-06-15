######################
 Plugin how-to guides
######################

This page provides task-oriented guides for creating each type of virtualenv plugin.

***************************
 Create a discovery plugin
***************************

Discovery plugins locate Python interpreters. Register your plugin under the ``virtualenv.discovery`` entry point group.

Implement the ``Discover`` interface:

.. code-block:: python

    from __future__ import annotations

    from argparse import ArgumentParser

    from virtualenv.config.cli.parser import VirtualEnvOptions
    from virtualenv.discovery.discover import Discover
    from virtualenv.discovery.py_info import PythonInfo


    class CustomDiscovery(Discover):
        @classmethod
        def add_parser_arguments(cls, parser: ArgumentParser) -> None:
            parser.add_argument("--custom-opt", help="custom discovery option")

        def __init__(self, options: VirtualEnvOptions) -> None:
            super().__init__(options)
            self.custom_opt = options.custom_opt

        def run(self) -> PythonInfo | None:
            # Locate Python interpreter and return PythonInfo
            return PythonInfo.from_exe(str(self._find_python()))

        def _find_python(self) -> str:
            # Implementation-specific logic
            ...

Register the entry point:

.. code-block:: ini

    [virtualenv.discovery]
    custom = your_package.discovery:CustomDiscovery

*************************
 Create a creator plugin
*************************

Creator plugins build the virtual environment structure. Register under ``virtualenv.create``.

Implement the ``Creator`` interface:

.. code-block:: python

    from __future__ import annotations

    from argparse import ArgumentParser

    from virtualenv.app_data.base import AppData
    from virtualenv.config.cli.parser import VirtualEnvOptions
    from virtualenv.create.creator import Creator, CreatorMeta
    from virtualenv.discovery.py_info import PythonInfo


    class CustomCreator(Creator):
        @classmethod
        def add_parser_arguments(
            cls,
            parser: ArgumentParser,
            interpreter: PythonInfo,
            meta: CreatorMeta,
            app_data: AppData,
        ) -> None:
            parser.add_argument("--custom-creator-opt", help="custom creator option")

        def __init__(self, options: VirtualEnvOptions, interpreter: PythonInfo) -> None:
            super().__init__(options, interpreter)
            self.custom_opt = options.custom_creator_opt

        def create(self) -> None:
            # Create directory structure
            self.bin_dir.mkdir(parents=True, exist_ok=True)
            # Copy or symlink Python executable
            self.install_python()
            # Set up site-packages
            self.install_site_packages()
            # Write pyvenv.cfg
            self.set_pyenv_cfg()

Register the entry point using a naming pattern that matches platform and Python version:

.. code-block:: ini

    [virtualenv.create]
    cpython3-posix = virtualenv.create.via_global_ref.builtin.cpython.cpython3:CPython3Posix
    cpython3-win = virtualenv.create.via_global_ref.builtin.cpython.cpython3:CPython3Windows

************************
 Create a seeder plugin
************************

Seeder plugins install initial packages into the virtual environment. Register under ``virtualenv.seed``.

Override ``cannot_seed`` to reject target interpreters the seeder does not support. The base returns ``None`` for every
interpreter; return a message instead and selection rejects the seeder before creating the environment, surfacing your
message to the user. A plugin can therefore serve Python versions the bundled seeders no longer ship wheels for, such as
a version past its support window.

Implement the ``Seeder`` interface:

.. code-block:: python

    from __future__ import annotations

    from argparse import ArgumentParser

    from virtualenv.app_data.base import AppData
    from virtualenv.config.cli.parser import VirtualEnvOptions
    from virtualenv.create.creator import Creator
    from virtualenv.discovery.py_info import PythonInfo
    from virtualenv.seed.seeder import Seeder


    class CustomSeeder(Seeder):
        @classmethod
        def add_parser_arguments(
            cls, parser: ArgumentParser, interpreter: PythonInfo, app_data: AppData
        ) -> None:
            parser.add_argument("--custom-seed-opt", help="custom seeder option")

        @classmethod
        def cannot_seed(cls, interpreter: PythonInfo) -> str | None:
            # ship wheels down to Python 3.6, for example
            if interpreter.version_info[:2] >= (3, 6):
                return None
            return "custom seeder ships wheels only for Python 3.6 and later"

        def __init__(self, options: VirtualEnvOptions, enabled: bool) -> None:
            super().__init__(options, enabled)
            self.custom_opt = options.custom_seed_opt

        def run(self, creator: Creator) -> None:
            # Install packages into creator.bin_dir / creator.script("pip")
            self._install_packages(creator)

        def _install_packages(self, creator: Creator) -> None:
            # Implementation-specific logic
            ...

Register the entry point:

.. code-block:: ini

    [virtualenv.seed]
    custom = your_package.seed:CustomSeeder

****************************
 Create an activator plugin
****************************

Activator plugins generate shell activation scripts. Register under ``virtualenv.activate``.

Implement the ``Activator`` interface:

.. code-block:: python

    from __future__ import annotations

    from pathlib import Path

    from virtualenv.activation.activator import Activator
    from virtualenv.create.creator import Creator


    class CustomShellActivator(Activator):
        def generate(self, creator: Creator) -> list[Path]:
            # Generate activation script content
            script_content = self._render_template(creator)
            # Write to activation directory
            dest = creator.bin_dir / self.script_name
            dest.write_text(script_content)
            return [dest]

        def _render_template(self, creator: Creator) -> str:
            # Return activation script content
            return f"""
            # Custom shell activation script
            export VIRTUAL_ENV="{creator.dest}"
            export PATH="{creator.bin_dir}:$PATH"
            """

        @property
        def script_name(self) -> str:
            return "activate.custom"

Register the entry point:

.. code-block:: ini

    [virtualenv.activate]
    bash = virtualenv.activation.bash:BashActivator
    fish = virtualenv.activation.fish:FishActivator
    custom = your_package.activation:CustomShellActivator

*********************************
 Package and distribute a plugin
*********************************

Use ``pyproject.toml`` to declare entry points:

.. code-block:: toml

    [project]
    name = "virtualenv-custom-plugin"
    version = "1.0.0"
    dependencies = ["virtualenv>=20.0.0"]

    [project.entry-points."virtualenv.discovery"]
    custom = "virtualenv_custom.discovery:CustomDiscovery"

    [project.entry-points."virtualenv.create"]
    custom-posix = "virtualenv_custom.creator:CustomCreator"

    [project.entry-points."virtualenv.seed"]
    custom = "virtualenv_custom.seeder:CustomSeeder"

    [project.entry-points."virtualenv.activate"]
    custom = "virtualenv_custom.activator:CustomActivator"

    [build-system]
    requires = ["setuptools>=61"]
    build-backend = "setuptools.build_meta"

Install your plugin alongside virtualenv:

.. code-block:: console

    $ pip install virtualenv-custom-plugin

Or in development mode:

.. code-block:: console

    $ pip install -e /path/to/virtualenv-custom-plugin

Test your plugin by creating a virtual environment:

.. code-block:: console

    $ virtualenv --discovery=custom --creator=custom-posix --seeder=custom --activators=custom test-env
