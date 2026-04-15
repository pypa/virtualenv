#####################
 Plugin architecture
#####################

This page explains how virtualenv's plugin system works internally.

**************
 Entry points
**************

virtualenv uses Python entry points (``setuptools`` / ``importlib.metadata``) to discover plugins. Each plugin registers
under one of four entry point groups:

- ``virtualenv.discovery``
- ``virtualenv.create``
- ``virtualenv.seed``
- ``virtualenv.activate``

At startup, virtualenv loads all registered entry points from these groups and makes them available as CLI options.
Built-in implementations are registered in virtualenv's own ``pyproject.toml``, while third-party plugins register their
entry points in their own package metadata.

When a package with virtualenv plugins is installed in the same environment as virtualenv, the plugins become
immediately available without additional configuration.

******************
 Plugin lifecycle
******************

The following diagram shows how plugins are discovered and executed:

.. mermaid::

    sequenceDiagram
        participant User
        participant CLI
        participant EntryPoints
        participant Discovery
        participant Creator
        participant Seeder
        participant Activator

        rect rgba(37, 99, 235, 0.15)
        User->>CLI: virtualenv myenv
        CLI->>EntryPoints: Load plugins from all groups
        EntryPoints-->>CLI: Available plugins
        CLI->>CLI: Build argument parser with plugin options
        CLI->>User: Parse CLI arguments
        User-->>CLI: Selected options
        end

        rect rgba(22, 163, 106, 0.15)
        CLI->>Discovery: Run selected discovery plugin
        Discovery-->>CLI: PythonInfo
        CLI->>Creator: Create environment with PythonInfo
        Creator-->>CLI: Created environment
        CLI->>Seeder: Seed packages into environment
        Seeder-->>CLI: Seeded environment
        CLI->>Activator: Generate activation scripts
        Activator-->>CLI: Complete environment
        end

The lifecycle follows these stages:

1. virtualenv starts and discovers all entry points from the four plugin groups
2. The CLI parser is built dynamically, incorporating options from all discovered plugins
3. User arguments are parsed to select which discovery, creator, seeder, and activator plugins to use
4. Selected plugins execute in sequence: discover → create → seed → activate
5. Each stage passes its output to the next stage

************************
 Extension point design
************************

Each extension point follows a consistent pattern:

Base abstract class
    Each extension point defines a base abstract class (``Discover``, ``Creator``, ``Seeder``, ``Activator``) that
    specifies the interface plugins must implement.

Built-in implementations
    virtualenv includes built-in implementations registered as entry points in its own ``pyproject.toml``. For example,
    the built-in CPython creator is registered as ``cpython3-posix``.

Third-party plugins
    External packages implement the base interface and register their own entry points under the same group. When
    installed, they appear alongside built-in options.

CLI selection
    Command-line flags (``--discovery``, ``--creator``, ``--seeder``, ``--activators``) allow users to select which
    implementation to use. Multiple activators can be selected simultaneously.

Parser integration
    Each plugin can contribute CLI arguments through the ``add_parser_arguments`` classmethod. These arguments appear in
    ``virtualenv --help`` and are available when the plugin is selected.

**********************
 How plugins interact
**********************

Plugins execute in a pipeline where each stage depends on the previous one:

Discovery → Creator
    The discovery plugin produces a ``PythonInfo`` object describing the source Python interpreter. This object contains
    metadata about the Python version, platform, paths, and capabilities. The creator plugin receives this
    ``PythonInfo`` and uses it to determine how to build the virtual environment structure.

Creator → Seeder
    The creator plugin produces a ``Creator`` object representing the newly created virtual environment. This includes
    paths to the environment's ``bin`` directory, site-packages, and Python executable. The seeder plugin uses these
    paths to install packages.

Seeder → Activator
    After seeding completes, activator plugins use the ``Creator`` object to generate shell activation scripts. These
    scripts reference the environment's bin directory and other paths to configure the shell environment.

This pipeline ensures that each plugin has the information it needs from previous stages. The ``PythonInfo`` flows from
discovery to creator, and the ``Creator`` object flows from creator to both seeder and activators.

Plugin isolation
================

Plugins within the same extension point do not interact with each other. Only one discovery and one creator plugin can
run per invocation, though multiple activators can run simultaneously. This isolation keeps plugins simple and focused
on their specific task.
