from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path

import pytest


@pytest.fixture
def _mock_registry(mocker):  # noqa: C901
    from virtualenv.discovery.windows.pep514 import winreg  # noqa: PLC0415

    loc, glob = {}, {}
    mock_value_str = (Path(__file__).parent / "winreg-mock-values.py").read_text(encoding="utf-8")
    exec(mock_value_str, glob, loc)  # noqa: S102
    enum_collect = loc["enum_collect"]
    value_collect = loc["value_collect"]
    key_open = loc["key_open"]
    hive_open = loc["hive_open"]

    def _enum_key(key, at):
        key_id = key.value if isinstance(key, Key) else key
        result = enum_collect[key_id][at]
        if isinstance(result, OSError):
            raise result
        return result

    mocker.patch.object(winreg, "EnumKey", side_effect=_enum_key)

    def _query_value_ex(key, value_name):
        key_id = key.value if isinstance(key, Key) else key
        result = value_collect[key_id][value_name]
        if isinstance(result, OSError):
            raise result
        return result

    mocker.patch.object(winreg, "QueryValueEx", side_effect=_query_value_ex)

    class Key:
        def __init__(self, value) -> None:
            self.value = value

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            return None

    @contextmanager
    def _open_key_ex(*args):
        if len(args) == 2:
            key, value = args
            key_id = key.value if isinstance(key, Key) else key
            result = Key(key_open[key_id][value])  # this needs to be something that can be with-ed, so let's wrap it
        elif len(args) == 4:
            result = hive_open[args]
        else:
            raise RuntimeError
        value = result.value if isinstance(result, Key) else result
        if isinstance(value, OSError):
            raise value
        yield result

    mocker.patch.object(winreg, "OpenKeyEx", side_effect=_open_key_ex)
    mocker.patch("os.path.exists", return_value=True)


def _mock_pyinfo(major, minor, arch, exe):
    """Return PythonInfo objects with essential metadata set for the given args"""
    from virtualenv.discovery.py_info import PythonInfo, VersionInfo  # noqa: PLC0415

    info = PythonInfo()
    info.base_prefix = str(Path(exe).parent)
    info.executable = info.original_executable = info.system_executable = exe
    info.implementation = "CPython"
    info.architecture = arch
    info.version_info = VersionInfo(major, minor, 0, "final", 0)
    return info


@pytest.fixture
def _populate_pyinfo_cache(monkeypatch):
    """Add metadata to virtualenv.discovery.cached_py_info._CACHE for all (mocked) registry entries"""
    import virtualenv.discovery.cached_py_info  # noqa: PLC0415

    # Data matches _mock_registry fixture
    interpreters = [
        ("ContinuumAnalytics", 3, 10, 32, "C:\\Users\\user\\Miniconda3\\python.exe", None),
        ("ContinuumAnalytics", 3, 10, 64, "C:\\Users\\user\\Miniconda3-64\\python.exe", None),
        ("PythonCore", 3, 9, 64, "C:\\Users\\user\\AppData\\Local\\Programs\\Python\\Python36\\python.exe", None),
        ("PythonCore", 3, 9, 64, "C:\\Users\\user\\AppData\\Local\\Programs\\Python\\Python36\\python.exe", None),
        ("PythonCore", 3, 5, 64, "C:\\Users\\user\\AppData\\Local\\Programs\\Python\\Python35\\python.exe", None),
        ("PythonCore", 3, 9, 64, "C:\\Users\\user\\AppData\\Local\\Programs\\Python\\Python36\\python.exe", None),
        ("PythonCore", 3, 7, 32, "C:\\Users\\user\\AppData\\Local\\Programs\\Python\\Python37-32\\python.exe", None),
        ("PythonCore", 3, 12, 64, "C:\\Users\\user\\AppData\\Local\\Programs\\Python\\Python312\\python.exe", None),
        ("PythonCore", 2, 7, 64, "C:\\Python27\\python.exe", None),
        ("PythonCore", 3, 4, 64, "C:\\Python34\\python.exe", None),
        ("CompanyA", 3, 6, 64, "Z:\\CompanyA\\Python\\3.6\\python.exe", None),
    ]
    for _, major, minor, arch, exe, _ in interpreters:
        info = _mock_pyinfo(major, minor, arch, exe)
        monkeypatch.setitem(virtualenv.discovery.cached_py_info._CACHE, Path(info.executable), info)  # noqa: SLF001
