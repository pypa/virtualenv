import pytest

from virtualenv.flavors.windows import WindowsFlavor


def test_activation_scripts():
    expected = set(["activate.bat", "activate.ps1", "deactivate.bat"])
    assert WindowsFlavor().activation_scripts == expected


@pytest.mark.parametrize(
    ("version_info", "expected"),
    [
        (
            [2, 6, 9, "final", 0],
            ["python.exe", "python2.exe", "python2.6.exe"],
        ),
        (
            [2, 7, 9, "final", 0],
            ["python.exe", "python2.exe", "python2.7.exe"],
        ),
        (
            [3, 2, 6, "final", 0],
            ["python.exe", "python3.exe", "python3.2.exe"],
        ),
        (
            [3, 3, 6, "final", 0],
            ["python.exe", "python3.exe", "python3.3.exe"],
        ),
        (
            [3, 4, 2, "final", 0],
            ["python.exe", "python3.exe", "python3.4.exe"],
        ),
    ],
)
def test_python_bins(version_info, expected):
    assert WindowsFlavor().python_bins({"sys.version_info": version_info}) == expected


@pytest.mark.parametrize(
    "version_info",
    [
        [2, 6, 9, "final", 0],
        [2, 7, 9, "final", 0],
        [3, 2, 6, "final", 0],
        [3, 3, 6, "final", 0],
        [3, 4, 2, "final", 0],
    ],
)
def test_lib_dir(version_info):
    assert WindowsFlavor().lib_dir({"sys.version_info": version_info}) == "Lib"
