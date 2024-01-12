from __future__ import annotations

import sys

import pytest

from virtualenv.discovery.py_spec import PythonSpec


@pytest.mark.skipif(sys.platform != "win32", reason="no Windows registry")
@pytest.mark.usefixtures("_mock_registry")
@pytest.mark.usefixtures("_populate_pyinfo_cache")
@pytest.mark.parametrize(
    ("string_spec", "expected_exe"),
    [
        # 64-bit over 32-bit
        ("python3.10", "C:\\Users\\user\\Miniconda3-64\\python.exe"),
        ("cpython3.10", "C:\\Users\\user\\Miniconda3-64\\python.exe"),
        # 1 installation of 3.9 available
        ("python3.12", "C:\\Users\\user\\AppData\\Local\\Programs\\Python\\Python312\\python.exe"),
        ("cpython3.12", "C:\\Users\\user\\AppData\\Local\\Programs\\Python\\Python312\\python.exe"),
        # resolves to highest available version
        ("python", "C:\\Users\\user\\AppData\\Local\\Programs\\Python\\Python312\\python.exe"),
        ("cpython", "C:\\Users\\user\\AppData\\Local\\Programs\\Python\\Python312\\python.exe"),
        # Non-standard org name
        ("python3.6", "Z:\\CompanyA\\Python\\3.6\\python.exe"),
        ("cpython3.6", "Z:\\CompanyA\\Python\\3.6\\python.exe"),
    ],
)
def test_propose_interpreters(string_spec, expected_exe):
    from virtualenv.discovery.windows import propose_interpreters  # noqa: PLC0415

    spec = PythonSpec.from_string_spec(string_spec)
    interpreter = next(propose_interpreters(spec=spec, cache_dir=None, env=None))
    assert interpreter.executable == expected_exe
