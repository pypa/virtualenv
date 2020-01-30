from __future__ import absolute_import, unicode_literals

import copy
import itertools
import json
import logging
import sys
from collections import namedtuple

import pytest

from virtualenv.discovery import cached_py_info
from virtualenv.discovery.py_info import CURRENT, PythonInfo, VersionInfo
from virtualenv.discovery.py_spec import PythonSpec
from virtualenv.info import fs_supports_symlink


def test_current_as_json():
    result = CURRENT.to_json()
    parsed = json.loads(result)
    a, b, c, d, e = sys.version_info
    assert parsed["version_info"] == {"major": a, "minor": b, "micro": c, "releaselevel": d, "serial": e}


def test_bad_exe_py_info_raise(tmp_path):
    exe = str(tmp_path)
    with pytest.raises(RuntimeError) as context:
        PythonInfo.from_exe(exe)
    msg = str(context.value)
    assert "code" in msg
    assert exe in msg


def test_bad_exe_py_info_no_raise(tmp_path, caplog, capsys):
    caplog.set_level(logging.NOTSET)
    exe = str(tmp_path)
    result = PythonInfo.from_exe(exe, raise_on_error=False)
    assert result is None
    out, _ = capsys.readouterr()
    assert not out
    messages = [r.message for r in caplog.records if r.filename != "filelock.py"]
    assert len(messages) == 2
    msg = messages[0]
    assert "get interpreter info via cmd: " in msg
    msg = messages[1]
    assert str(exe) in msg
    assert "code" in msg


@pytest.mark.parametrize(
    "spec",
    itertools.chain(
        [sys.executable],
        list(
            "{}{}{}".format(impl, ".".join(str(i) for i in ver), arch)
            for impl, ver, arch in itertools.product(
                ([CURRENT.implementation] + (["python"] if CURRENT.implementation == "CPython" else [])),
                [sys.version_info[0 : i + 1] for i in range(3)],
                ["", "-{}".format(CURRENT.architecture)],
            )
        ),
    ),
)
def test_satisfy_py_info(spec):
    parsed_spec = PythonSpec.from_string_spec(spec)
    matches = CURRENT.satisfies(parsed_spec, True)
    assert matches is True


def test_satisfy_not_arch():
    parsed_spec = PythonSpec.from_string_spec(
        "{}-{}".format(CURRENT.implementation, 64 if CURRENT.architecture == 32 else 32)
    )
    matches = CURRENT.satisfies(parsed_spec, True)
    assert matches is False


def _generate_not_match_current_interpreter_version():
    result = []
    for i in range(3):
        ver = sys.version_info[0 : i + 1]
        for a in range(len(ver)):
            for o in [-1, 1]:
                temp = list(ver)
                temp[a] += o
                result.append(".".join(str(i) for i in temp))
    return result


_NON_MATCH_VER = _generate_not_match_current_interpreter_version()


@pytest.mark.parametrize("spec", _NON_MATCH_VER)
def test_satisfy_not_version(spec):
    parsed_spec = PythonSpec.from_string_spec("{}{}".format(CURRENT.implementation, spec))
    matches = CURRENT.satisfies(parsed_spec, True)
    assert matches is False


def test_py_info_cached_error(mocker, tmp_path):
    spy = mocker.spy(cached_py_info, "_run_subprocess")
    with pytest.raises(RuntimeError):
        PythonInfo.from_exe(str(tmp_path))
    with pytest.raises(RuntimeError):
        PythonInfo.from_exe(str(tmp_path))
    assert spy.call_count == 1


@pytest.mark.skipif(not fs_supports_symlink(), reason="symlink is not supported")
def test_py_info_cached_symlink_error(mocker, tmp_path):
    spy = mocker.spy(cached_py_info, "_run_subprocess")
    with pytest.raises(RuntimeError):
        PythonInfo.from_exe(str(tmp_path))
    symlinked = tmp_path / "a"
    symlinked.symlink_to(tmp_path)
    with pytest.raises(RuntimeError):
        PythonInfo.from_exe(str(symlinked))
    assert spy.call_count == 1


def test_py_info_cache_clear(mocker, tmp_path):
    spy = mocker.spy(cached_py_info, "_run_subprocess")
    assert PythonInfo.from_exe(sys.executable) is not None
    assert spy.call_count == 1
    PythonInfo.clear_cache()
    assert PythonInfo.from_exe(sys.executable) is not None
    assert spy.call_count == 2


@pytest.mark.skipif(not fs_supports_symlink(), reason="symlink is not supported")
def test_py_info_cached_symlink(mocker, tmp_path):
    spy = mocker.spy(cached_py_info, "_run_subprocess")
    first_result = PythonInfo.from_exe(sys.executable)
    assert first_result is not None
    assert spy.call_count == 1

    new_exe = tmp_path / "a"
    new_exe.symlink_to(sys.executable)
    new_exe_str = str(new_exe)
    second_result = PythonInfo.from_exe(new_exe_str)
    assert second_result.executable == new_exe_str
    assert spy.call_count == 1


PyInfoMock = namedtuple("PyInfoMock", ["implementation", "architecture", "version_info"])


@pytest.mark.parametrize(
    "target, position, discovered",
    [
        (
            PyInfoMock("CPython", 64, VersionInfo(3, 6, 8, "final", 0)),
            0,
            [
                PyInfoMock("CPython", 64, VersionInfo(3, 6, 9, "final", 0)),
                PyInfoMock("PyPy", 64, VersionInfo(3, 6, 8, "final", 0)),
            ],
        ),
        (
            PyInfoMock("CPython", 64, VersionInfo(3, 6, 8, "final", 0)),
            0,
            [
                PyInfoMock("CPython", 64, VersionInfo(3, 6, 9, "final", 0)),
                PyInfoMock("CPython", 32, VersionInfo(3, 6, 9, "final", 0)),
            ],
        ),
        (
            PyInfoMock("CPython", 64, VersionInfo(3, 8, 1, "final", 0)),
            0,
            [
                PyInfoMock("CPython", 32, VersionInfo(2, 7, 12, "rc", 2)),
                PyInfoMock("PyPy", 64, VersionInfo(3, 8, 1, "final", 0)),
            ],
        ),
    ],
)
def test_system_executable_no_exact_match(target, discovered, position, tmp_path, mocker, caplog):
    """Here we should fallback to other compatible"""

    def _make_py_info(of):
        base = copy.deepcopy(CURRENT)
        base.implementation = of.implementation
        base.version_info = of.version_info
        base.architecture = of.architecture
        return base

    discovered_with_path = {}
    names = []
    selected = None
    for pos, i in enumerate(discovered):
        path = tmp_path / str(pos)
        path.write_text("")
        py_info = _make_py_info(i)
        if pos == position:
            selected = py_info
        discovered_with_path[str(path)] = py_info
        names.append(path.name)

    target_py_info = _make_py_info(target)
    mocker.patch.object(target_py_info, "_find_possible_exe_names", return_value=names)
    mocker.patch.object(target_py_info, "_find_possible_folders", return_value=[str(tmp_path)])
    mocker.patch.object(target_py_info, "from_exe", side_effect=lambda k: discovered_with_path[k])
    target_py_info._system_executable = None
    target_py_info.real_prefix = str(tmp_path)

    path = target_py_info.system_executable

    found = discovered_with_path[path]
    assert found is selected

    assert caplog.text
