"""Test that PKG_CONFIG_PATH is properly set and restored during activation/deactivation."""

from __future__ import annotations

from argparse import Namespace

import pytest

from virtualenv.activation import (
    BashActivator,
    BatchActivator,
    CShellActivator,
    FishActivator,
    NushellActivator,
    PowerShellActivator,
    PythonActivator,
)
from virtualenv.info import IS_WIN


def _create_test_env(tmp_path):
    """Helper to create a mock virtualenv environment for testing."""

    class MockInterpreter:
        tcl_lib = None
        tk_lib = None

    class MockCreator:
        def __init__(self, dest):
            self.dest = dest
            self.bin_dir = dest / ("Scripts" if IS_WIN else "bin")
            self.bin_dir.mkdir(parents=True)
            self.interpreter = MockInterpreter()
            self.pyenv_cfg = {}
            self.env_name = "test-env"

    return MockCreator(tmp_path)


@pytest.mark.parametrize(
    ("activator_class", "script_name", "search_patterns"),
    [
        (
            BashActivator,
            "activate",
            {
                "save": '_OLD_PKG_CONFIG_PATH="${PKG_CONFIG_PATH}"',
                "set": 'PKG_CONFIG_PATH="${VIRTUAL_ENV}/lib/pkgconfig:${PKG_CONFIG_PATH}"',
                "export": "export PKG_CONFIG_PATH",
                "restore": 'PKG_CONFIG_PATH="$_OLD_PKG_CONFIG_PATH"',
                "unset": "unset _OLD_PKG_CONFIG_PATH",
            },
        ),
        (
            FishActivator,
            "activate.fish",
            {
                "save": "set -gx _OLD_PKG_CONFIG_PATH",
                "set": 'set -gx PKG_CONFIG_PATH "$VIRTUAL_ENV/lib/pkgconfig:$PKG_CONFIG_PATH"',
                "restore": "set -gx PKG_CONFIG_PATH",
                "erase": "set -e _OLD_PKG_CONFIG_PATH",
            },
        ),
        (
            CShellActivator,
            "activate.csh",
            {
                "save": 'set _OLD_PKG_CONFIG_PATH="$PKG_CONFIG_PATH"',
                "set": 'setenv PKG_CONFIG_PATH "${VIRTUAL_ENV}/lib/pkgconfig:${PKG_CONFIG_PATH}"',
                "deactivate_test": "test $?_OLD_PKG_CONFIG_PATH != 0",
                "restore": 'setenv PKG_CONFIG_PATH "$_OLD_PKG_CONFIG_PATH:q"',
                "unset": "unset _OLD_PKG_CONFIG_PATH",
            },
        ),
    ],
)
def test_pkg_config_path_unix_shells(tmp_path, activator_class, script_name, search_patterns):
    """Test PKG_CONFIG_PATH is set for Unix-like shells."""
    if IS_WIN and activator_class in {BashActivator, FishActivator, CShellActivator}:
        pytest.skip("Unix shell test on Windows")

    creator = _create_test_env(tmp_path)
    options = Namespace(prompt=None)
    activator = activator_class(options)

    # Generate the activation script
    activator.generate(creator)

    # Read the generated script
    script_path = creator.bin_dir / script_name
    content = script_path.read_text(encoding="utf-8")

    # Verify all expected patterns are present
    for pattern_name, pattern in search_patterns.items():
        assert pattern in content, f"Missing {pattern_name} pattern: {pattern}\nScript content:\n{content}"


@pytest.mark.skipif(not IS_WIN, reason="Windows-only test")
@pytest.mark.parametrize(
    ("activator_class", "script_name", "search_patterns"),
    [
        (
            BatchActivator,
            "activate.bat",
            {
                "save": 'set "_OLD_PKG_CONFIG_PATH=%PKG_CONFIG_PATH%"',
                "set": 'set "PKG_CONFIG_PATH=%VIRTUAL_ENV%\\lib\\pkgconfig;%PKG_CONFIG_PATH%"',
            },
        ),
        (
            PowerShellActivator,
            "activate.ps1",
            {
                "save": "New-Variable -Scope global -Name _OLD_PKG_CONFIG_PATH",
                "set": '$env:PKG_CONFIG_PATH = "$env:VIRTUAL_ENV\\lib\\pkgconfig;$env:PKG_CONFIG_PATH"',
                "restore": "$env:PKG_CONFIG_PATH = $variable:_OLD_PKG_CONFIG_PATH",
                "remove": 'Remove-Variable "_OLD_PKG_CONFIG_PATH" -Scope global',
            },
        ),
    ],
)
def test_pkg_config_path_windows_shells(tmp_path, activator_class, script_name, search_patterns):
    """Test PKG_CONFIG_PATH is set for Windows shells."""
    creator = _create_test_env(tmp_path)
    options = Namespace(prompt=None)
    activator = activator_class(options)

    # Generate the activation script
    activator.generate(creator)

    # Read the generated script
    script_path = creator.bin_dir / script_name
    content = script_path.read_text(encoding="utf-8")

    # Verify all expected patterns are present
    for pattern_name, pattern in search_patterns.items():
        assert pattern in content, f"Missing {pattern_name} pattern: {pattern}\nScript content:\n{content}"


def test_pkg_config_path_python_activator(tmp_path):
    """Test PKG_CONFIG_PATH is set in Python activator."""
    creator = _create_test_env(tmp_path)
    # Add libs attribute needed by PythonActivator
    creator.libs = [tmp_path / "Lib" / "site-packages"]
    options = Namespace(prompt=None)
    activator = PythonActivator(options)

    # Generate the activation script
    activator.generate(creator)

    # Read the generated script
    script_path = creator.bin_dir / "activate_this.py"
    content = script_path.read_text(encoding="utf-8")

    # Verify PKG_CONFIG_PATH is handled
    assert "PKG_CONFIG_PATH" in content, f"PKG_CONFIG_PATH not found in activate_this.py:\n{content}"
    assert "pkg_config_path" in content, f"pkg_config_path variable not found in activate_this.py:\n{content}"


def test_pkg_config_path_nushell(tmp_path):
    """Test PKG_CONFIG_PATH is set in Nushell."""
    creator = _create_test_env(tmp_path)
    options = Namespace(prompt=None)
    activator = NushellActivator(options)

    # Generate the activation script
    activator.generate(creator)

    # Read the generated script
    script_path = creator.bin_dir / "activate.nu"
    content = script_path.read_text(encoding="utf-8")

    # Verify PKG_CONFIG_PATH is handled
    assert "PKG_CONFIG_PATH" in content, f"PKG_CONFIG_PATH not found in activate.nu:\n{content}"
    assert "old_pkg_config_path" in content, f"old_pkg_config_path variable not saved in activate.nu:\n{content}"
    assert "new_pkg_config_path" in content, f"new_pkg_config_path variable not found in activate.nu:\n{content}"
