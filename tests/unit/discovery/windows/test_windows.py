import sys

import pytest

from virtualenv.discovery.py_spec import PythonSpec
from virtualenv.discovery.windows import propose_interpreters


@pytest.mark.skipif(sys.platform != "win32", reason="no Windows registry")
@pytest.mark.usefixtures("_mock_registry")
@pytest.mark.usefixtures("_populate_pyinfo_cache")
@pytest.mark.parametrize(
    ("string_spec", "expected_exe"),
    [
        # 64-bit over 32-bit
        ("python3.7", "C:\\Users\\user\\Miniconda3-64\\python.exe"),
        ("cpython3.7", "C:\\Users\\user\\Miniconda3-64\\python.exe"),
        # 1 installation of 3.9 available
        ("python3.9", "C:\\Users\\user\\AppData\\Local\\Programs\\Python\\Python36\\python.exe"),
        ("cpython3.9", "C:\\Users\\user\\AppData\\Local\\Programs\\Python\\Python36\\python.exe"),
        # resolves to highest available version
        ("python", "C:\\Users\\user\\AppData\\Local\\Programs\\Python\\Python36\\python.exe"),
        ("cpython", "C:\\Users\\user\\AppData\\Local\\Programs\\Python\\Python36\\python.exe"),
    ],
)
def test_propose_interpreters(string_spec, expected_exe):
    spec = PythonSpec.from_string_spec(string_spec)
    interpreter = next(propose_interpreters(spec=spec, cache_dir=None, env=None))
    assert interpreter.executable == expected_exe
