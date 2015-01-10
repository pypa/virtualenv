import posixpath

import pytest

from virtualenv.flavors.posix import PosixFlavor


def test_activation_scripts():
    expected = set(["activate.sh", "activate.fish", "activate.csh"])
    assert PosixFlavor().activation_scripts == expected


@pytest.mark.parametrize(
    ("version_info", "expected"),
    [
        ([2, 6, 9, "final", 0], ["python", "python2", "python2.6"]),
        ([2, 7, 9, "final", 0], ["python", "python2", "python2.7"]),
        ([3, 2, 6, "final", 0], ["python", "python3", "python3.2"]),
        ([3, 3, 6, "final", 0], ["python", "python3", "python3.3"]),
        ([3, 4, 2, "final", 0], ["python", "python3", "python3.4"]),
    ],
)
def test_python_bins(version_info, expected):
    assert PosixFlavor().python_bins({"sys.version_info": version_info}) == expected


@pytest.mark.parametrize(
    ("version_info", "expected"),
    [
        ([2, 6, 9, "final", 0], posixpath.join("lib", "python2.6")),
        ([2, 7, 9, "final", 0], posixpath.join("lib", "python2.7")),
        ([3, 2, 6, "final", 0], posixpath.join("lib", "python3.2")),
        ([3, 3, 6, "final", 0], posixpath.join("lib", "python3.3")),
        ([3, 4, 2, "final", 0], posixpath.join("lib", "python3.4")),
    ],
)
def test_lib_dir(version_info, expected):
    assert PosixFlavor().lib_dir({"sys.version_info": version_info}) == expected
