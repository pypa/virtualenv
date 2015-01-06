import subprocess

import pretend
import pytest

from virtualenv.builders.venv import VenvBuilder, _SCRIPT


def test_venv_builder_check_available_success(monkeypatch):
    check_output = pretend.call_recorder(lambda *a, **kw: None)
    monkeypatch.setattr(subprocess, "check_output", check_output)

    assert VenvBuilder.check_available("wat")
    assert check_output.calls == [
        pretend.call(["wat", "-c", "import venv"], stderr=subprocess.STDOUT),
    ]


def test_venv_builder_check_available_fails(monkeypatch):
    @pretend.call_recorder
    def check_output(*args, **kwargs):
        raise subprocess.CalledProcessError(1, "an error!")

    monkeypatch.setattr(subprocess, "check_output", check_output)

    assert not VenvBuilder.check_available("wat")
    assert check_output.calls == [
        pretend.call(["wat", "-c", "import venv"], stderr=subprocess.STDOUT),
    ]


@pytest.mark.parametrize("system_site_packages", [True, False])
def test_venv_builder_create_venv(tmpdir, monkeypatch, system_site_packages):
    check_call = pretend.call_recorder(lambda *a, **kw: None)
    monkeypatch.setattr(subprocess, "check_call", check_call)
    builder = VenvBuilder(
        "wat",
        None,
        system_site_packages=system_site_packages,
    )
    builder.create_virtual_environment(str(tmpdir))

    script = _SCRIPT.format(
        system_site_packages=system_site_packages,
        destination=str(tmpdir),
    )

    assert check_call.calls == [
        pretend.call(["wat", "-c", script])
    ]
