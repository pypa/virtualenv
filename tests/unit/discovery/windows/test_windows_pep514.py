from __future__ import annotations

import sys
import textwrap

import pytest


@pytest.mark.skipif(sys.platform != "win32", reason="no Windows registry")
@pytest.mark.usefixtures("_mock_registry")
def test_pep514():
    from virtualenv.discovery.windows.pep514 import discover_pythons  # noqa: PLC0415

    interpreters = list(discover_pythons())
    assert interpreters == [
        ("ContinuumAnalytics", 3, 10, 32, False, "C:\\Users\\user\\Miniconda3\\python.exe", None),
        ("ContinuumAnalytics", 3, 10, 64, False, "C:\\Users\\user\\Miniconda3-64\\python.exe", None),
        (
            "PythonCore",
            3,
            9,
            64,
            False,
            "C:\\Users\\user\\AppData\\Local\\Programs\\Python\\Python39\\python.exe",
            None,
        ),
        (
            "PythonCore",
            3,
            9,
            64,
            False,
            "C:\\Users\\user\\AppData\\Local\\Programs\\Python\\Python39\\python.exe",
            None,
        ),
        (
            "PythonCore",
            3,
            8,
            64,
            False,
            "C:\\Users\\user\\AppData\\Local\\Programs\\Python\\Python38\\python.exe",
            None,
        ),
        (
            "PythonCore",
            3,
            9,
            64,
            False,
            "C:\\Users\\user\\AppData\\Local\\Programs\\Python\\Python39\\python.exe",
            None,
        ),
        (
            "PythonCore",
            3,
            10,
            32,
            False,
            "C:\\Users\\user\\AppData\\Local\\Programs\\Python\\Python310-32\\python.exe",
            None,
        ),
        (
            "PythonCore",
            3,
            12,
            64,
            False,
            "C:\\Users\\user\\AppData\\Local\\Programs\\Python\\Python312\\python.exe",
            None,
        ),
        (
            "PythonCore",
            3,
            13,
            64,
            True,
            "C:\\Users\\user\\AppData\\Local\\Programs\\Python\\Python313\\python3.13t.exe",
            None,
        ),
        ("CompanyA", 3, 6, 64, False, "Z:\\CompanyA\\Python\\3.6\\python.exe", None),
        ("PythonCore", 2, 7, 64, False, "C:\\Python27\\python.exe", None),
        ("PythonCore", 3, 7, 64, False, "C:\\Python37\\python3.exe", None),
    ]


@pytest.mark.skipif(sys.platform != "win32", reason="no Windows registry")
@pytest.mark.usefixtures("_mock_registry")
def test_pep514_run(capsys, caplog):
    from virtualenv.discovery.windows import pep514  # noqa: PLC0415

    pep514._run()  # noqa: SLF001
    out, err = capsys.readouterr()
    expected = textwrap.dedent(
        r"""
    ('CompanyA', 3, 6, 64, False, 'Z:\\CompanyA\\Python\\3.6\\python.exe', None)
    ('ContinuumAnalytics', 3, 10, 32, False, 'C:\\Users\\user\\Miniconda3\\python.exe', None)
    ('ContinuumAnalytics', 3, 10, 64, False, 'C:\\Users\\user\\Miniconda3-64\\python.exe', None)
    ('PythonCore', 2, 7, 64, False, 'C:\\Python27\\python.exe', None)
    ('PythonCore', 3, 10, 32, False, 'C:\\Users\\user\\AppData\\Local\\Programs\\Python\\Python310-32\\python.exe', None)
    ('PythonCore', 3, 12, 64, False, 'C:\\Users\\user\\AppData\\Local\\Programs\\Python\\Python312\\python.exe', None)
    ('PythonCore', 3, 13, 64, True, 'C:\\Users\\user\\AppData\\Local\\Programs\\Python\\Python313\\python3.13t.exe', None)
    ('PythonCore', 3, 7, 64, False, 'C:\\Python37\\python3.exe', None)
    ('PythonCore', 3, 8, 64, False, 'C:\\Users\\user\\AppData\\Local\\Programs\\Python\\Python38\\python.exe', None)
    ('PythonCore', 3, 9, 64, False, 'C:\\Users\\user\\AppData\\Local\\Programs\\Python\\Python39\\python.exe', None)
    ('PythonCore', 3, 9, 64, False, 'C:\\Users\\user\\AppData\\Local\\Programs\\Python\\Python39\\python.exe', None)
    ('PythonCore', 3, 9, 64, False, 'C:\\Users\\user\\AppData\\Local\\Programs\\Python\\Python39\\python.exe', None)
    """,  # noqa: E501
    ).strip()
    assert out.strip() == expected
    assert not err
    prefix = "PEP-514 violation in Windows Registry at "
    expected_logs = [
        f"{prefix}HKEY_CURRENT_USER/PythonCore/3.1/SysArchitecture error: invalid format magic",
        f"{prefix}HKEY_CURRENT_USER/PythonCore/3.2/SysArchitecture error: arch is not string: 100",
        f"{prefix}HKEY_CURRENT_USER/PythonCore/3.3 error: no ExecutablePath or default for it",
        f"{prefix}HKEY_CURRENT_USER/PythonCore/3.3 error: could not load exe with value None",
        f"{prefix}HKEY_CURRENT_USER/PythonCore/3.11/InstallPath error: missing",
        f"{prefix}HKEY_CURRENT_USER/PythonCore/3.12/SysVersion error: invalid format magic",
        f"{prefix}HKEY_CURRENT_USER/PythonCore/3.X/SysVersion error: version is not string: 2778",
        f"{prefix}HKEY_CURRENT_USER/PythonCore/3.X error: invalid format 3.X",
    ]
    assert caplog.messages == expected_logs


@pytest.mark.skipif(sys.platform != "win32", reason="no Windows registry")
def test_pep514_python3_fallback(mocker, tmp_path):
    from virtualenv.discovery.windows import pep514
    from virtualenv.discovery.windows.pep514 import winreg

    # Create a mock python3.exe, but no python.exe
    python3_exe = tmp_path / "python3.exe"
    python3_exe.touch()
    mocker.patch("os.path.exists", side_effect=lambda p: str(p) == str(python3_exe))

    # Mock winreg functions to simulate a single Python installation
    mock_key = mocker.MagicMock()
    mocker.patch.object(winreg, "OpenKeyEx", return_value=mock_key)

    enum_key_map = {
        mock_key: ["PythonCore"],
        "PythonCore": ["3.9-32"],
        "3.9-32": ["InstallPath"],
    }

    def enum_key(key, at):
        if key in enum_key_map and at < len(enum_key_map[key]):
            return enum_key_map[key][at]
        raise StopIteration

    mocker.patch.object(winreg, "EnumKey", side_effect=enum_key)

    def get_value(key, name):
        if name == "ExecutablePath":
            raise FileNotFoundError
        if name is None:
            return str(tmp_path)
        return "3.9"

    mocker.patch.object(winreg, "QueryValueEx", side_effect=get_value)
    mocker.patch.object(pep514, "load_arch_data", return_value=64)
    mocker.patch.object(pep514, "load_threaded", return_value=False)

    interpreters = list(pep514.discover_pythons())

    assert interpreters == [("PythonCore", 3, 9, 64, False, str(python3_exe), None)]
