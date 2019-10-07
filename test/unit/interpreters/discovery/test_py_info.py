from __future__ import absolute_import, unicode_literals

import itertools
import json
import logging
import sys

import pytest

from virtualenv.interpreters.discovery import CURRENT, PythonInfo, PythonSpec


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
    out, err = capsys.readouterr()
    assert not out
    assert not err
    assert len(caplog.messages) == 1
    msg = caplog.messages[0]
    assert repr(exe) in msg
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
