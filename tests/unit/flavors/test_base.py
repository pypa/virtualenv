import os
import subprocess

import pretend
import pytest

from virtualenv.flavors.base import BaseFlavor


def test_base_flavor_execute(monkeypatch):
    fake_check_call = pretend.call_recorder(lambda cmd, env: None)

    monkeypatch.setattr(subprocess, "check_call", fake_check_call)
    monkeypatch.setattr(os, "environ", {"a": "thing"})

    BaseFlavor().execute("foo", wat="lol")

    assert fake_check_call.calls == [
        pretend.call("foo", env={"wat": "lol", "a": "thing"}),
    ]


class TestBaseFlavorNotImplemented:

    def test_activation_scripts(self):
        flavor = BaseFlavor()
        with pytest.raises(NotImplementedError):
            flavor.activation_scripts

    def test_python_bins(self):
        flavor = BaseFlavor()
        with pytest.raises(NotImplementedError):
            flavor.python_bins(None)

    def test_lib_dir(self):
        flavor = BaseFlavor()
        with pytest.raises(NotImplementedError):
            flavor.lib_dir(None)
