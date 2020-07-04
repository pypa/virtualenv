from __future__ import absolute_import, unicode_literals

import copy
import itertools
import json
import logging
import os
import sys
from collections import namedtuple
from textwrap import dedent

import pytest

from virtualenv.discovery import cached_py_info
from virtualenv.discovery.py_info import PythonInfo, VersionInfo
from virtualenv.discovery.py_spec import PythonSpec
from virtualenv.info import fs_supports_symlink
from virtualenv.util.path import Path

CURRENT = PythonInfo.current_system()


def test_current_as_json():
    result = CURRENT._to_json()
    parsed = json.loads(result)
    a, b, c, d, e = sys.version_info
    assert parsed["version_info"] == {"major": a, "minor": b, "micro": c, "releaselevel": d, "serial": e}


def test_bad_exe_py_info_raise(tmp_path, session_app_data):
    exe = str(tmp_path)
    with pytest.raises(RuntimeError) as context:
        PythonInfo.from_exe(exe, session_app_data)
    msg = str(context.value)
    assert "code" in msg
    assert exe in msg


def test_bad_exe_py_info_no_raise(tmp_path, caplog, capsys, session_app_data):
    caplog.set_level(logging.NOTSET)
    exe = str(tmp_path)
    result = PythonInfo.from_exe(exe, session_app_data, raise_on_error=False)
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
                (
                    [CURRENT.implementation]
                    + (["python"] if CURRENT.implementation == "CPython" else [])
                    + (
                        [CURRENT.implementation.lower()]
                        if CURRENT.implementation != CURRENT.implementation.lower()
                        else []
                    )
                ),
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
        "{}-{}".format(CURRENT.implementation, 64 if CURRENT.architecture == 32 else 32),
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


def test_py_info_cached_error(mocker, tmp_path, session_app_data):
    spy = mocker.spy(cached_py_info, "_run_subprocess")
    with pytest.raises(RuntimeError):
        PythonInfo.from_exe(str(tmp_path), session_app_data)
    with pytest.raises(RuntimeError):
        PythonInfo.from_exe(str(tmp_path), session_app_data)
    assert spy.call_count == 1


@pytest.mark.skipif(not fs_supports_symlink(), reason="symlink is not supported")
def test_py_info_cached_symlink_error(mocker, tmp_path, session_app_data):
    spy = mocker.spy(cached_py_info, "_run_subprocess")
    with pytest.raises(RuntimeError):
        PythonInfo.from_exe(str(tmp_path), session_app_data)
    symlinked = tmp_path / "a"
    symlinked.symlink_to(tmp_path)
    with pytest.raises(RuntimeError):
        PythonInfo.from_exe(str(symlinked), session_app_data)
    assert spy.call_count == 2


def test_py_info_cache_clear(mocker, tmp_path, session_app_data):
    spy = mocker.spy(cached_py_info, "_run_subprocess")
    result = PythonInfo.from_exe(sys.executable, session_app_data)
    assert result is not None
    count = 1 if result.executable == sys.executable else 2  # at least two, one for the venv, one more for the host
    assert spy.call_count >= count
    PythonInfo.clear_cache(session_app_data)
    assert PythonInfo.from_exe(sys.executable, session_app_data) is not None
    assert spy.call_count >= 2 * count


@pytest.mark.skipif(not fs_supports_symlink(), reason="symlink is not supported")
def test_py_info_cached_symlink(mocker, tmp_path, session_app_data):
    spy = mocker.spy(cached_py_info, "_run_subprocess")
    first_result = PythonInfo.from_exe(sys.executable, session_app_data)
    assert first_result is not None
    count = spy.call_count
    # at least two, one for the venv, one more for the host
    exp_count = 1 if first_result.executable == sys.executable else 2
    assert count >= exp_count  # at least two, one for the venv, one more for the host

    new_exe = tmp_path / "a"
    new_exe.symlink_to(sys.executable)
    pyvenv = Path(sys.executable).parents[1] / "pyvenv.cfg"
    if pyvenv.exists():
        (tmp_path / pyvenv.name).write_text(pyvenv.read_text())
    new_exe_str = str(new_exe)
    second_result = PythonInfo.from_exe(new_exe_str, session_app_data)
    assert second_result.executable == new_exe_str
    assert spy.call_count == count + 1  # no longer needed the host invocation, but the new symlink is must


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
def test_system_executable_no_exact_match(target, discovered, position, tmp_path, mocker, caplog, session_app_data):
    """Here we should fallback to other compatible"""
    caplog.set_level(logging.DEBUG)

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
        py_info.system_executable = CURRENT.system_executable
        py_info.executable = CURRENT.system_executable
        py_info.base_executable = str(path)
        if pos == position:
            selected = py_info
        discovered_with_path[str(path)] = py_info
        names.append(path.name)

    target_py_info = _make_py_info(target)
    mocker.patch.object(target_py_info, "_find_possible_exe_names", return_value=names)
    mocker.patch.object(target_py_info, "_find_possible_folders", return_value=[str(tmp_path)])

    # noinspection PyUnusedLocal
    def func(k, app_data, resolve_to_host, raise_on_error):
        return discovered_with_path[k]

    mocker.patch.object(target_py_info, "from_exe", side_effect=func)
    target_py_info.real_prefix = str(tmp_path)

    target_py_info.system_executable = None
    target_py_info.executable = str(tmp_path)
    mapped = target_py_info._resolve_to_system(session_app_data, target_py_info)
    assert mapped.system_executable == CURRENT.system_executable
    found = discovered_with_path[mapped.base_executable]
    assert found is selected

    assert caplog.records[0].msg == "discover exe for %s in %s"
    for record in caplog.records[1:-1]:
        assert record.message.startswith("refused interpreter ")
        assert record.levelno == logging.DEBUG

    warn_similar = caplog.records[-1]
    assert warn_similar.levelno == logging.DEBUG
    assert warn_similar.msg.startswith("no exact match found, chosen most similar")


def test_py_info_ignores_distutils_config(monkeypatch, tmp_path):
    (tmp_path / "setup.cfg").write_text(
        dedent(
            """
            [install]
            prefix={0}{1}prefix
            install_purelib={0}{1}purelib
            install_platlib={0}{1}platlib
            install_headers={0}{1}headers
            install_scripts={0}{1}scripts
            install_data={0}{1}data
            """.format(
                tmp_path, os.sep,
            ),
        ),
    )
    monkeypatch.chdir(tmp_path)
    py_info = PythonInfo.from_exe(sys.executable)
    distutils = py_info.distutils_install
    for key, value in distutils.items():
        assert not value.startswith(str(tmp_path)), "{}={}".format(key, value)


def test_discover_exe_on_path_non_spec_name_match(mocker):
    suffixed_name = "python{}.{}m".format(CURRENT.version_info.major, CURRENT.version_info.minor)
    if sys.platform == "win32":
        suffixed_name += Path(CURRENT.original_executable).suffix
    spec = PythonSpec.from_string_spec(suffixed_name)
    mocker.patch.object(CURRENT, "original_executable", str(Path(CURRENT.executable).parent / suffixed_name))
    assert CURRENT.satisfies(spec, impl_must_match=True) is True


def test_discover_exe_on_path_non_spec_name_not_match(mocker):
    suffixed_name = "python{}.{}m".format(CURRENT.version_info.major, CURRENT.version_info.minor)
    if sys.platform == "win32":
        suffixed_name += Path(CURRENT.original_executable).suffix
    spec = PythonSpec.from_string_spec(suffixed_name)
    mocker.patch.object(
        CURRENT, "original_executable", str(Path(CURRENT.executable).parent / "e{}".format(suffixed_name)),
    )
    assert CURRENT.satisfies(spec, impl_must_match=True) is False


def test_py_info_setuptools():
    from setuptools.dist import Distribution

    assert Distribution
    PythonInfo()


def test_py_info_to_system_raises(session_app_data, mocker, caplog, skip_if_test_in_system):
    caplog.set_level(logging.DEBUG)
    mocker.patch.object(PythonInfo, "_find_possible_folders", return_value=[])
    result = PythonInfo.from_exe(sys.executable, app_data=session_app_data, raise_on_error=False)
    assert result is None
    log = caplog.records[-1]
    assert log.levelno == logging.INFO
    expected = "ignore {} due cannot resolve system due to RuntimeError('failed to detect ".format(sys.executable)
    assert expected in log.message
