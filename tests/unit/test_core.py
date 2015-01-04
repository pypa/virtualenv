import os
import sys

import pretend
import pytest

import virtualenv.core

from virtualenv.core import create, select_builder, select_flavor
from virtualenv.builders.legacy import LegacyBuilder
from virtualenv.builders.venv import VenvBuilder
from virtualenv.flavors.posix import PosixFlavor
from virtualenv.flavors.windows import WindowsFlavor


class TestCreate:

    def test_default_python(self, monkeypatch):
        fake_builder_instance = pretend.stub(
            create=pretend.call_recorder(lambda dest: None),
        )
        fake_builder_type = pretend.call_recorder(
            lambda *a, **kw: fake_builder_instance
        )
        fake_select_builder = pretend.call_recorder(
            lambda p: fake_builder_type
        )
        monkeypatch.setattr(
            virtualenv.core,
            "select_builder",
            fake_select_builder,
        )

        fake_flavor_instance = pretend.stub()
        fake_flavor_type = pretend.call_recorder(lambda: fake_flavor_instance)
        fake_select_flavor = pretend.call_recorder(lambda: fake_flavor_type)
        monkeypatch.setattr(
            virtualenv.core,
            "select_flavor",
            fake_select_flavor,
        )

        create("/fake/", lol="wat")

        assert fake_select_builder.calls == [pretend.call(None)]
        assert fake_builder_type.calls == [
            pretend.call(python=None, flavor=fake_flavor_instance, lol="wat"),
        ]
        assert fake_builder_instance.create.calls == [
            pretend.call("/fake/"),
        ]
        assert fake_select_flavor.calls == [pretend.call()]
        assert fake_flavor_type.calls == [pretend.call()]

    def test_explicit_python(self, monkeypatch):
        fake_builder_instance = pretend.stub(
            create=pretend.call_recorder(lambda dest: None),
        )
        fake_builder_type = pretend.call_recorder(
            lambda *a, **kw: fake_builder_instance
        )
        fake_select_builder = pretend.call_recorder(
            lambda p: fake_builder_type
        )
        monkeypatch.setattr(
            virtualenv.core,
            "select_builder",
            fake_select_builder,
        )

        fake_flavor_instance = pretend.stub()
        fake_flavor_type = pretend.call_recorder(lambda: fake_flavor_instance)
        fake_select_flavor = pretend.call_recorder(lambda: fake_flavor_type)
        monkeypatch.setattr(
            virtualenv.core,
            "select_flavor",
            fake_select_flavor,
        )

        fake_python = pretend.stub()

        create("/fake/", python=fake_python, lol="wat")

        assert fake_select_builder.calls == [pretend.call(fake_python)]
        assert fake_builder_type.calls == [
            pretend.call(
                python=fake_python,
                flavor=fake_flavor_instance,
                lol="wat",
            ),
        ]
        assert fake_builder_instance.create.calls == [
            pretend.call("/fake/"),
        ]
        assert fake_select_flavor.calls == [pretend.call()]
        assert fake_flavor_type.calls == [pretend.call()]


class TestSelectBuilder:

    def test_default_python(self, monkeypatch):
        fake_executable = pretend.stub()
        fake_builder = pretend.stub(
            check_available=pretend.call_recorder(lambda x: True)
        )
        monkeypatch.setattr(sys, "executable", fake_executable)

        select_builder(None, builders=[fake_builder])

        assert fake_builder.check_available.calls == [
            pretend.call(fake_executable),
        ]

    def test_explicit_python(self, monkeypatch):
        fake_python = pretend.stub()
        fake_builder = pretend.stub(
            check_available=pretend.call_recorder(lambda x: True)
        )

        select_builder(fake_python, builders=[fake_builder])

        assert fake_builder.check_available.calls == [
            pretend.call(fake_python),
        ]

    def test_default_builders(self):
        assert select_builder(None) in [VenvBuilder, LegacyBuilder]

    def test_no_available_builders(self):
        fake_builder = pretend.stub(
            check_available=pretend.call_recorder(lambda x: False),
        )

        with pytest.raises(RuntimeError):
            select_builder(None, builders=[fake_builder])

        assert fake_builder.check_available.calls == [
            pretend.call(sys.executable),
        ]

    def test_no_builders(self):
        with pytest.raises(RuntimeError):
            select_builder(None, builders=[])


class TestSelectFlavor:

    def test_windows(self, monkeypatch):
        monkeypatch.setattr(sys, "platform", "win32")
        assert select_flavor() is WindowsFlavor

    def test_windows_ironpython(self, monkeypatch):
        monkeypatch.setattr(sys, "platform", "cli")
        monkeypatch.setattr(os, "name", "nt")
        assert select_flavor() is WindowsFlavor

    def test_posix(self, monkeypatch):
        monkeypatch.setattr(sys, "platform", "linux2")
        assert select_flavor() is PosixFlavor
