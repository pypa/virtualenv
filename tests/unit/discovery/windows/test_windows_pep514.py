import sys
import textwrap

import pytest


@pytest.mark.skipif(sys.platform != "win32", reason="no Windows registry")
@pytest.mark.usefixtures("_mock_registry")
def test_pep514():
    from virtualenv.discovery.windows.pep514 import discover_pythons

    interpreters = list(discover_pythons())
    assert interpreters == [
        ("ContinuumAnalytics", 3, 7, 32, "C:\\Users\\user\\Miniconda3\\python.exe", None),
        ("ContinuumAnalytics", 3, 7, 64, "C:\\Users\\user\\Miniconda3-64\\python.exe", None),
        ("PythonCore", 3, 6, 64, "C:\\Users\\user\\AppData\\Local\\Programs\\Python\\Python36\\python.exe", None),
        ("PythonCore", 3, 6, 64, "C:\\Users\\user\\AppData\\Local\\Programs\\Python\\Python36\\python.exe", None),
        ("PythonCore", 3, 5, 64, "C:\\Users\\user\\AppData\\Local\\Programs\\Python\\Python35\\python.exe", None),
        ("PythonCore", 3, 6, 64, "C:\\Users\\user\\AppData\\Local\\Programs\\Python\\Python36\\python.exe", None),
        ("PythonCore", 3, 7, 32, "C:\\Users\\user\\AppData\\Local\\Programs\\Python\\Python37-32\\python.exe", None),
        ("PythonCore", 3, 9, 64, "C:\\Users\\user\\AppData\\Local\\Programs\\Python\\Python36\\python.exe", None),
        ("CompanyA", 3, 3, 64, "Z:\\CompanyA\\Python\\3.3\\python.exe", None),
        ("PythonCore", 2, 7, 64, "C:\\Python27\\python.exe", None),
        ("PythonCore", 3, 4, 64, "C:\\Python34\\python.exe", None),
    ]


@pytest.mark.skipif(sys.platform != "win32", reason="no Windows registry")
@pytest.mark.usefixtures("_mock_registry")
def test_pep514_run(capsys, caplog):
    from virtualenv.discovery.windows import pep514

    pep514._run()
    out, err = capsys.readouterr()
    expected = textwrap.dedent(
        r"""
    ('CompanyA', 3, 3, 64, 'Z:\\CompanyA\\Python\\3.3\\python.exe', None)
    ('ContinuumAnalytics', 3, 7, 32, 'C:\\Users\\user\\Miniconda3\\python.exe', None)
    ('ContinuumAnalytics', 3, 7, 64, 'C:\\Users\\user\\Miniconda3-64\\python.exe', None)
    ('PythonCore', 2, 7, 64, 'C:\\Python27\\python.exe', None)
    ('PythonCore', 3, 4, 64, 'C:\\Python34\\python.exe', None)
    ('PythonCore', 3, 5, 64, 'C:\\Users\\user\\AppData\\Local\\Programs\\Python\\Python35\\python.exe', None)
    ('PythonCore', 3, 6, 64, 'C:\\Users\\user\\AppData\\Local\\Programs\\Python\\Python36\\python.exe', None)
    ('PythonCore', 3, 6, 64, 'C:\\Users\\user\\AppData\\Local\\Programs\\Python\\Python36\\python.exe', None)
    ('PythonCore', 3, 6, 64, 'C:\\Users\\user\\AppData\\Local\\Programs\\Python\\Python36\\python.exe', None)
    ('PythonCore', 3, 7, 32, 'C:\\Users\\user\\AppData\\Local\\Programs\\Python\\Python37-32\\python.exe', None)
    ('PythonCore', 3, 9, 64, 'C:\\Users\\user\\AppData\\Local\\Programs\\Python\\Python36\\python.exe', None)
    """,
    ).strip()
    assert out.strip() == expected
    assert not err
    prefix = "PEP-514 violation in Windows Registry at "
    expected_logs = [
        f"{prefix}HKEY_CURRENT_USER/PythonCore/3.1/SysArchitecture error: invalid format magic",
        f"{prefix}HKEY_CURRENT_USER/PythonCore/3.2/SysArchitecture error: arch is not string: 100",
        f"{prefix}HKEY_CURRENT_USER/PythonCore/3.3 error: no ExecutablePath or default for it",
        f"{prefix}HKEY_CURRENT_USER/PythonCore/3.3 error: could not load exe with value None",
        f"{prefix}HKEY_CURRENT_USER/PythonCore/3.8/InstallPath error: missing",
        f"{prefix}HKEY_CURRENT_USER/PythonCore/3.9/SysVersion error: invalid format magic",
        f"{prefix}HKEY_CURRENT_USER/PythonCore/3.X/SysVersion error: version is not string: 2778",
        f"{prefix}HKEY_CURRENT_USER/PythonCore/3.X error: invalid format 3.X",
    ]
    assert caplog.messages == expected_logs
