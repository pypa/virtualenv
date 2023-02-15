from collections import defaultdict
from contextlib import contextmanager
from pathlib import Path

import pytest


@pytest.fixture()
def _mock_registry(mocker):
    from virtualenv.discovery.windows.pep514 import winreg

    loc, glob = {}, {}
    mock_value_str = (Path(__file__).parent / "winreg-mock-values.py").read_text()
    exec(mock_value_str, glob, loc)
    enum_collect = loc["enum_collect"]
    value_collect = loc["value_collect"]
    key_open = loc["key_open"]
    hive_open = loc["hive_open"]

    def _e(key, at):
        key_id = key.value if isinstance(key, Key) else key
        result = enum_collect[key_id][at]
        if isinstance(result, OSError):
            raise result
        return result

    mocker.patch.object(winreg, "EnumKey", side_effect=_e)

    def _v(key, value_name):
        key_id = key.value if isinstance(key, Key) else key
        result = value_collect[key_id][value_name]
        if isinstance(result, OSError):
            raise result
        return result

    mocker.patch.object(winreg, "QueryValueEx", side_effect=_v)

    class Key:
        def __init__(self, value):
            self.value = value

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):  # noqa: U100
            return None

    @contextmanager
    def _o(*args):
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

    mocker.patch.object(winreg, "OpenKeyEx", side_effect=_o)
    mocker.patch("os.path.exists", return_value=True)


@pytest.fixture()
def _collect_winreg_access(mocker):
    # noinspection PyUnresolvedReferences
    from winreg import EnumKey, OpenKeyEx, QueryValueEx

    from virtualenv.discovery.windows.pep514 import winreg

    hive_open = {}
    key_open = defaultdict(dict)

    @contextmanager
    def _c(*args):
        res = None
        key_id = id(args[0]) if len(args) == 2 else None
        try:
            with OpenKeyEx(*args) as c:
                res = id(c)
                yield c
        except Exception as exception:
            res = exception
            raise exception
        finally:
            if len(args) == 4:
                hive_open[args] = res
            elif len(args) == 2:
                key_open[key_id][args[1]] = res

    enum_collect = defaultdict(list)

    def _e(key, at):
        result = None
        key_id = id(key)
        try:
            result = EnumKey(key, at)
            return result
        except Exception as exception:
            result = exception
            raise result
        finally:
            enum_collect[key_id].append(result)

    value_collect = defaultdict(dict)

    def _v(key, value_name):
        result = None
        key_id = id(key)
        try:
            result = QueryValueEx(key, value_name)
            return result
        except Exception as exception:
            result = exception
            raise result
        finally:
            value_collect[key_id][value_name] = result

    mocker.patch.object(winreg, "EnumKey", side_effect=_e)
    mocker.patch.object(winreg, "QueryValueEx", side_effect=_v)
    mocker.patch.object(winreg, "OpenKeyEx", side_effect=_c)

    yield

    print("")
    print(f"hive_open = {hive_open}")
    print(f"key_open = {dict(key_open.items())}")
    print(f"value_collect = {dict(value_collect.items())}")
    print(f"enum_collect = {dict(enum_collect.items())}")


def _mock_pyinfo(major, minor, arch, exe):
    """Return PythonInfo objects with essential metadata set for the given args"""
    from virtualenv.discovery.py_info import PythonInfo, VersionInfo

    info = PythonInfo()
    info.base_prefix = str(Path(exe).parent)
    info.executable = info.original_executable = info.system_executable = exe
    info.implementation = "CPython"
    info.architecture = arch
    info.version_info = VersionInfo(major, minor, 0, 'final', 0)
    return info


@pytest.fixture()
def _populate_pyinfo_cache(monkeypatch):
    """Add metadata to virtualenv.discovery.cached_py_info._CACHE for all (mocked) registry entries"""
    import virtualenv.discovery.cached_py_info

    # Data matches _mock_registry fixture
    interpreters = [
        ("ContinuumAnalytics", 3, 7, 32, "C:\\Users\\user\\Miniconda3\\python.exe", None),
        ("ContinuumAnalytics", 3, 7, 64, "C:\\Users\\user\\Miniconda3-64\\python.exe", None),
        ("PythonCore", 3, 6, 64, "C:\\Users\\user\\AppData\\Local\\Programs\\Python\\Python36\\python.exe", None),
        ("PythonCore", 3, 6, 64, "C:\\Users\\user\\AppData\\Local\\Programs\\Python\\Python36\\python.exe", None),
        ("PythonCore", 3, 5, 64, "C:\\Users\\user\\AppData\\Local\\Programs\\Python\\Python35\\python.exe", None),
        ("PythonCore", 3, 6, 64, "C:\\Users\\user\\AppData\\Local\\Programs\\Python\\Python36\\python.exe", None),
        ("PythonCore", 3, 7, 32, "C:\\Users\\user\\AppData\\Local\\Programs\\Python\\Python37-32\\python.exe", None),
        ("PythonCore", 3, 9, 64, "C:\\Users\\user\\AppData\\Local\\Programs\\Python\\Python36\\python.exe", None),
        ("PythonCore", 2, 7, 64, "C:\\Python27\\python.exe", None),
        ("PythonCore", 3, 4, 64, "C:\\Python34\\python.exe", None),
    ]
    for _, major, minor, arch, exe, _ in interpreters:
        info = _mock_pyinfo(major, minor, arch, exe)
        monkeypatch.setitem(virtualenv.discovery.cached_py_info._CACHE, Path(info.executable), info)
