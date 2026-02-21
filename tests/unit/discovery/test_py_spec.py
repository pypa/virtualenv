from __future__ import annotations

import sys
from copy import copy

import pytest

from virtualenv.discovery.py_spec import PythonSpec
from virtualenv.util.specifier import SimpleSpecifierSet as SpecifierSet


def test_bad_py_spec():
    text = "python2.3.4.5"
    spec = PythonSpec.from_string_spec(text)
    assert text in repr(spec)
    assert spec.str_spec == text
    assert spec.path == text
    content = vars(spec)
    del content["str_spec"]
    del content["path"]
    assert all(v is None for v in content.values())


def test_py_spec_first_digit_only_major():
    spec = PythonSpec.from_string_spec("278")
    assert spec.major == 2
    assert spec.minor == 78


def test_spec_satisfies_path_ok():
    spec = PythonSpec.from_string_spec(sys.executable)
    assert spec.satisfies(spec) is True


def test_spec_satisfies_path_nok(tmp_path):
    spec = PythonSpec.from_string_spec(sys.executable)
    of = PythonSpec.from_string_spec(str(tmp_path))
    assert spec.satisfies(of) is False


def test_spec_satisfies_arch():
    spec_1 = PythonSpec.from_string_spec("python-32")
    spec_2 = PythonSpec.from_string_spec("python-64")

    assert spec_1.satisfies(spec_1) is True
    assert spec_2.satisfies(spec_1) is False


def test_spec_satisfies_free_threaded():
    spec_1 = PythonSpec.from_string_spec("python3.13t")
    spec_2 = PythonSpec.from_string_spec("python3.13")

    assert spec_1.satisfies(spec_1) is True
    assert spec_1.free_threaded is True
    assert spec_2.satisfies(spec_1) is False
    assert spec_2.free_threaded is False


@pytest.mark.parametrize(
    ("req", "spec"),
    [("py", "python"), ("jython", "jython"), ("CPython", "cpython")],
)
def test_spec_satisfies_implementation_ok(req, spec):
    spec_1 = PythonSpec.from_string_spec(req)
    spec_2 = PythonSpec.from_string_spec(spec)
    assert spec_1.satisfies(spec_1) is True
    assert spec_2.satisfies(spec_1) is True


def test_spec_satisfies_implementation_nok():
    spec_1 = PythonSpec.from_string_spec("cpython")
    spec_2 = PythonSpec.from_string_spec("jython")
    assert spec_2.satisfies(spec_1) is False
    assert spec_1.satisfies(spec_2) is False


def _version_satisfies_pairs():
    target = set()
    version = tuple(str(i) for i in sys.version_info[0:3])
    for threading in (False, True):
        for i in range(len(version) + 1):
            req = ".".join(version[0:i])
            for j in range(i + 1):
                sat = ".".join(version[0:j])
                # can be satisfied in both directions
                if sat:
                    target.add((req, sat))
                # else: no version => no free-threading info
                target.add((sat, req))
                if not threading or not sat or not req:
                    # free-threading info requires a version
                    continue
                target.add((f"{req}t", f"{sat}t"))
                target.add((f"{sat}t", f"{req}t"))

    return sorted(target)


@pytest.mark.parametrize(("req", "spec"), _version_satisfies_pairs())
def test_version_satisfies_ok(req, spec):
    req_spec = PythonSpec.from_string_spec(f"python{req}")
    sat_spec = PythonSpec.from_string_spec(f"python{spec}")
    assert sat_spec.satisfies(req_spec) is True


def _version_not_satisfies_pairs():
    target = set()
    version = tuple(str(i) for i in sys.version_info[0:3])
    for major in range(len(version)):
        req = ".".join(version[0 : major + 1])
        for minor in range(major + 1):
            sat_ver = list(sys.version_info[0 : minor + 1])
            for patch in range(minor + 1):
                for o in [1, -1]:
                    temp = copy(sat_ver)
                    temp[patch] += o
                    if temp[patch] < 0:
                        continue
                    sat = ".".join(str(i) for i in temp)
                    target.add((req, sat))
    return sorted(target)


@pytest.mark.parametrize(("req", "spec"), _version_not_satisfies_pairs())
def test_version_satisfies_nok(req, spec):
    req_spec = PythonSpec.from_string_spec(f"python{req}")
    sat_spec = PythonSpec.from_string_spec(f"python{spec}")
    assert sat_spec.satisfies(req_spec) is False


def test_relative_spec(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    a_relative_path = str((tmp_path / "a" / "b").relative_to(tmp_path))
    spec = PythonSpec.from_string_spec(a_relative_path)
    assert spec.path == a_relative_path


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        (">=3.12", ">=3.12"),
        ("python>=3.12", ">=3.12"),
        ("cpython!=3.11.*", "!=3.11.*"),
        ("<=3.13,>=3.12", "<=3.13,>=3.12"),
    ],
)
def test_specifier_parsing(text, expected):
    spec = PythonSpec.from_string_spec(text)
    assert spec.version_specifier == SpecifierSet(expected)


def test_specifier_with_implementation():
    spec = PythonSpec.from_string_spec("cpython>=3.12")
    assert spec.implementation == "cpython"
    assert spec.version_specifier == SpecifierSet(">=3.12")


def test_specifier_satisfies_with_partial_information():
    spec = PythonSpec.from_string_spec(">=3.12")
    candidate = PythonSpec.from_string_spec("python3.12")
    assert candidate.satisfies(spec) is True


# --- Machine (ISA) tests ---


@pytest.mark.parametrize(
    ("spec_str", "expected_machine"),
    [
        ("cpython3.12-64-arm64", "arm64"),
        ("cpython3.12-64-x86_64", "x86_64"),
        ("cpython3.12-32-x86", "x86"),
        ("cpython3.12-64-aarch64", "aarch64"),
        ("cpython3.12-64-ppc64le", "ppc64le"),
        ("cpython3.12-64-s390x", "s390x"),
        ("cpython3.12-64-riscv64", "riscv64"),
        ("cpython3.12-64", None),  # no machine suffix
        ("cpython3.12", None),  # no arch, no machine
        ("python3.12-64-arm64", "arm64"),
    ],
)
def test_spec_parse_machine(spec_str, expected_machine):
    spec = PythonSpec.from_string_spec(spec_str)
    assert spec.machine == expected_machine


@pytest.mark.parametrize(
    ("spec_str", "expected_arch", "expected_machine"),
    [
        ("cpython3.12-64-arm64", 64, "arm64"),
        ("cpython3.12-32-x86", 32, "x86"),
        ("cpython3.12-64", 64, None),
    ],
)
def test_spec_parse_arch_and_machine_together(spec_str, expected_arch, expected_machine):
    spec = PythonSpec.from_string_spec(spec_str)
    assert spec.architecture == expected_arch
    assert spec.machine == expected_machine


def test_spec_satisfies_machine_match():
    spec_arm = PythonSpec.from_string_spec("cpython3.12-64-arm64")
    spec_arm2 = PythonSpec.from_string_spec("cpython3.12-64-arm64")
    assert spec_arm.satisfies(spec_arm2) is True


def test_spec_satisfies_machine_mismatch():
    spec_arm = PythonSpec.from_string_spec("cpython3.12-64-arm64")
    spec_x86 = PythonSpec.from_string_spec("cpython3.12-64-x86_64")
    assert spec_arm.satisfies(spec_x86) is False
    assert spec_x86.satisfies(spec_arm) is False


def test_spec_satisfies_machine_none_matches_any():
    """When spec has no machine constraint, any machine should match."""
    spec_no_machine = PythonSpec.from_string_spec("cpython3.12-64")
    spec_arm = PythonSpec.from_string_spec("cpython3.12-64-arm64")
    # candidate with machine satisfies a spec without machine constraint
    assert spec_arm.satisfies(spec_no_machine) is True


def test_spec_satisfies_machine_normalization():
    """Cross-OS ISA aliases should match: amd64 == x86_64, aarch64 == arm64."""
    from virtualenv.discovery.py_spec import _normalize_isa

    # amd64 (Windows) should normalize to x86_64
    assert _normalize_isa("amd64") == _normalize_isa("x86_64")
    # aarch64 (Linux) should normalize to arm64 (macOS)
    assert _normalize_isa("aarch64") == _normalize_isa("arm64")
    # Already-canonical values are unchanged
    assert _normalize_isa("x86_64") == "x86_64"
    assert _normalize_isa("arm64") == "arm64"
    assert _normalize_isa("x86") == "x86"
    assert _normalize_isa("ppc64le") == "ppc64le"
    assert _normalize_isa("riscv64") == "riscv64"
    assert _normalize_isa("s390x") == "s390x"


def test_spec_satisfies_machine_cross_os_aliases():
    """Specs using cross-OS ISA aliases should satisfy each other."""
    spec_amd64 = PythonSpec.from_string_spec("cpython3.12-64-amd64")
    spec_x86_64 = PythonSpec.from_string_spec("cpython3.12-64-x86_64")
    # amd64 and x86_64 are aliases, should satisfy each other
    assert spec_amd64.satisfies(spec_x86_64) is True
    assert spec_x86_64.satisfies(spec_amd64) is True

    spec_aarch64 = PythonSpec.from_string_spec("cpython3.12-64-aarch64")
    spec_arm64 = PythonSpec.from_string_spec("cpython3.12-64-arm64")
    # aarch64 and arm64 are aliases, should satisfy each other
    assert spec_aarch64.satisfies(spec_arm64) is True
    assert spec_arm64.satisfies(spec_aarch64) is True


def test_spec_repr_includes_machine():
    spec = PythonSpec.from_string_spec("cpython3.12-64-arm64")
    r = repr(spec)
    assert "machine=arm64" in r
    assert "architecture=64" in r


def test_spec_repr_no_machine():
    spec = PythonSpec.from_string_spec("cpython3.12-64")
    r = repr(spec)
    assert "machine=" not in r
    assert "architecture=64" in r
