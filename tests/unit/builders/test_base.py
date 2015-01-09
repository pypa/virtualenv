import glob
import itertools
import os
import os.path
import sys

import pretend
import pytest

from virtualenv.builders.base import BaseBuilder, WHEEL_DIR
from virtualenv.flavors.posix import PosixFlavor
from virtualenv.flavors.windows import WindowsFlavor


def test_base_builder_no_python():
    assert BaseBuilder(None, None).python == sys.executable


def test_base_builder_explicit_python():
    assert BaseBuilder("lol", None).python == "lol"


def test_base_builder_no_extra_search_dirs():
    assert BaseBuilder(None, None).extra_search_dirs == []


def test_base_builder_with_extra_search_dirs():
    builder = BaseBuilder(None, None, extra_search_dirs=["/place/"])
    assert builder.extra_search_dirs == ["/place/"]


def test_base_builder_check_available():
    with pytest.raises(NotImplementedError):
        BaseBuilder.check_available(None)


@pytest.mark.parametrize("clear", [True, False])
def test_base_builder_create(clear):
    builder = BaseBuilder(None, None, clear=clear)
    builder.clear_virtual_environment = pretend.call_recorder(lambda x: None)
    builder.create_virtual_environment = pretend.call_recorder(lambda x: None)
    builder.install_scripts = pretend.call_recorder(lambda x: None)
    builder.install_tools = pretend.call_recorder(lambda x: None)
    builder.create("/a/")

    if clear:
        assert builder.clear_virtual_environment.calls == [pretend.call(os.path.realpath(os.path.normpath("/a")))]
    else:
        assert builder.clear_virtual_environment.calls == []

    assert builder.create_virtual_environment.calls == [pretend.call(os.path.realpath(os.path.normpath("/a")))]
    assert builder.install_scripts.calls == [pretend.call(os.path.realpath(os.path.normpath("/a")))]
    assert builder.install_tools.calls == [pretend.call(os.path.realpath(os.path.normpath("/a")))]


def test_base_builder_clear_environment_doesnt_exist(tmpdir):
    envdir = str(tmpdir.join("env"))
    builder = BaseBuilder(None, None, clear=True)
    builder.clear_virtual_environment(envdir)
    assert not os.path.exists(envdir)


def test_base_builder_clear_environment_exists(tmpdir):
    envdir = str(tmpdir.join("env"))
    os.makedirs(envdir)
    assert os.path.exists(envdir)
    builder = BaseBuilder(None, None, clear=True)
    builder.clear_virtual_environment(envdir)
    assert not os.path.exists(envdir)


def test_base_builder_create_virtual_environment():
    builder = BaseBuilder(None, None)
    with pytest.raises(NotImplementedError):
        builder.create_virtual_environment(None)


@pytest.mark.parametrize("flavor", [PosixFlavor(), WindowsFlavor()])
def test_base_builder_install_scripts(tmpdir, flavor):
    envdir = str(tmpdir)
    bindir = str(tmpdir.join(flavor.bin_dir({"is_pypy": False})))
    os.makedirs(bindir)

    builder = BaseBuilder(None, flavor)
    builder.install_scripts(envdir)

    files = flavor.activation_scripts.copy()
    files.add("activate_this.py")
    assert set(os.listdir(bindir)) == files


@pytest.mark.parametrize(
    ("flavor", "pip", "setuptools", "extra_search_dirs"),
    itertools.product(
        # flavor
        [PosixFlavor(), WindowsFlavor()],
        # pip
        [True, False],
        # setuptools
        [True, False],
        # extra_search_dirs
        [[], ["/tmp/nothing/"], ["/tmp/nothing/", "/tmp/other/"]],
    ),
)
def test_base_builder_install_tools(tmpdir, flavor, pip, setuptools,
                                    extra_search_dirs):
    flavor.execute = pretend.call_recorder(lambda *a, **kw: None)

    class TestBuilder(BaseBuilder):
        _python_bin = '?'
        _python_info = {
            "sys.version_info": (2, 7, 9)
        }

    builder = TestBuilder(
        None,
        flavor,
        pip=pip,
        setuptools=setuptools,
        extra_search_dirs=extra_search_dirs,
    )
    builder.install_tools(str(tmpdir))

    projects = []
    if pip:
        projects.append("pip")
    if setuptools:
        projects.append("setuptools")

    if not pip and not setuptools:
        assert flavor.execute.calls == []
    else:
        assert flavor.execute.calls == [
            pretend.call(
                [
                    str(tmpdir.join(flavor.bin_dir({"is_pypy": False}), flavor.python_bin)),
                    "-m", "pip", "install", "--no-index", "--isolated",
                    "--ignore-installed",
                    "--find-links", WHEEL_DIR,
                ]
                + list(
                    itertools.chain.from_iterable(
                        ["--find-links", sd] for sd in extra_search_dirs
                    )
                )
                + projects,
                PYTHONPATH=os.pathsep.join(
                    glob.glob(os.path.join(WHEEL_DIR, "*.whl")),
                ),
                VIRTUALENV_BOOTSTRAP_ADJUST_EGGINSERT="-1",
            )
        ]
