# -*- coding: utf-8 -*-
from __future__ import absolute_import, unicode_literals

import atexit
import logging
import os
import shutil
import sys
import tempfile
from functools import partial

import coverage
import pytest
import six

from virtualenv import dirs
from virtualenv.discovery.py_info import PythonInfo
from virtualenv.info import IS_PYPY, IS_WIN, fs_supports_symlink
from virtualenv.report import LOGGER
from virtualenv.util.path import Path

_TEST_SETUP_DIR = tempfile.mkdtemp()
dirs._DATA_DIR = dirs.ReentrantFileLock(_TEST_SETUP_DIR)
atexit.register(lambda: shutil.rmtree(_TEST_SETUP_DIR))


def pytest_addoption(parser):
    parser.addoption("--int", action="store_true", default=False, help="run integration tests")


def pytest_collection_modifyitems(config, items):
    int_location = os.path.join("tests", "integration", "").rstrip()
    if len(items) == 1:
        return

    items.sort(key=lambda i: 2 if i.location[0].startswith(int_location) else (1 if "slow" in i.keywords else 0))

    if not config.getoption("--int"):
        for item in items:
            if item.location[0].startswith(int_location):
                item.add_marker(pytest.mark.skip(reason="need --int option to run"))


@pytest.fixture(scope="session")
def has_symlink_support(tmp_path_factory):
    return fs_supports_symlink()


@pytest.fixture(scope="session")
def link_folder(has_symlink_support):
    if has_symlink_support:
        return os.symlink
    elif sys.platform == "win32" and sys.version_info[0:2] > (3, 4):
        # on Windows junctions may be used instead
        import _winapi  # Cpython3.5 has builtin implementation for junctions

        return getattr(_winapi, "CreateJunction", None)
    else:
        return None


@pytest.fixture(scope="session")
def link_file(has_symlink_support):
    if has_symlink_support:
        return os.symlink
    else:
        return None


@pytest.fixture(scope="session")
def link(link_folder, link_file):
    def _link(src, dest):
        clean = dest.unlink
        s_dest = str(dest)
        s_src = str(src)
        if src.is_dir():
            if link_folder:
                link_folder(s_src, s_dest)
            else:
                shutil.copytree(s_src, s_dest)
                clean = partial(shutil.rmtree, str(dest))
        else:
            if link_file:
                link_file(s_src, s_dest)
            else:
                shutil.copy2(s_src, s_dest)
        return clean

    return _link


@pytest.fixture(autouse=True)
def ensure_logging_stable():
    logger_level = LOGGER.level
    handlers = [i for i in LOGGER.handlers]
    filelock_logger = logging.getLogger("filelock")
    fl_level = filelock_logger.level
    yield
    filelock_logger.setLevel(fl_level)
    for handler in LOGGER.handlers:
        LOGGER.removeHandler(handler)
    for handler in handlers:
        LOGGER.addHandler(handler)
    LOGGER.setLevel(logger_level)


@pytest.fixture(autouse=True)
def check_cwd_not_changed_by_test():
    old = os.getcwd()
    yield
    new = os.getcwd()
    if old != new:
        pytest.fail("tests changed cwd: {!r} => {!r}".format(old, new))


@pytest.fixture(autouse=True)
def ensure_py_info_cache_empty():
    PythonInfo.clear_cache()
    yield
    PythonInfo.clear_cache()


@pytest.fixture(autouse=True)
def ignore_global_config(tmp_path, mocker, monkeypatch):
    mocker.patch("virtualenv.dirs._CFG_DIR", None)
    mocker.patch("virtualenv.dirs.user_config_dir", return_value=Path(str(tmp_path / "this-should-never-exist")))
    yield


@pytest.fixture(autouse=True)
def check_os_environ_stable():
    old = os.environ.copy()
    # ensure we don't inherit parent env variables
    to_clean = {
        k
        for k in os.environ.keys()
        if k.startswith(str("VIRTUALENV_")) or str("VIRTUAL_ENV") in k or k.startswith(str("TOX_"))
    }
    cleaned = {k: os.environ[k] for k, v in os.environ.items()}
    os.environ[str("VIRTUALENV_NO_DOWNLOAD")] = str("1")
    is_exception = False
    try:
        yield
    except BaseException:
        is_exception = True
        raise
    finally:
        try:
            del os.environ[str("VIRTUALENV_NO_DOWNLOAD")]
            if is_exception is False:
                new = os.environ
                extra = {k: new[k] for k in set(new) - set(old)}
                miss = {k: old[k] for k in set(old) - set(new) - to_clean}
                diff = {
                    "{} = {} vs {}".format(k, old[k], new[k])
                    for k in set(old) & set(new)
                    if old[k] != new[k] and not k.startswith(str("PYTEST_"))
                }
                if extra or miss or diff:
                    msg = "tests changed environ"
                    if extra:
                        msg += " extra {}".format(extra)
                    if miss:
                        msg += " miss {}".format(miss)
                    if diff:
                        msg += " diff {}".format(diff)
                    pytest.fail(msg)
        finally:
            os.environ.update(cleaned)


COV_ENV_VAR = "COVERAGE_PROCESS_START"
COVERAGE_RUN = os.environ.get(str(COV_ENV_VAR))


@pytest.fixture(autouse=True)
def coverage_env(monkeypatch, link):
    """
    Enable coverage report collection on the created virtual environments by injecting the coverage project
    """
    if COVERAGE_RUN:
        # we inject right after creation, we cannot collect coverage on site.py - used for helper scripts, such as debug
        from virtualenv import run

        def via_cli(args, options=None):
            session = prev_run(args, options)
            old_run = session.creator.run

            def create_run():
                result = old_run()
                obj["cov"] = EnableCoverage(link)
                obj["cov"].__enter__(session.creator)
                return result

            monkeypatch.setattr(session.creator, "run", create_run)
            return session

        obj = {"cov": None}
        prev_run = run.session_via_cli
        monkeypatch.setattr(run, "session_via_cli", via_cli)

        def finish():
            cov = obj["cov"]
            obj["cov"] = None
            cov.__exit__(None, None, None)

        yield finish
        if obj["cov"]:
            finish()

    else:

        def finish():
            pass

        yield finish


class EnableCoverage(object):
    _COV_FILE = Path(coverage.__file__)
    _COV_SITE_PACKAGES = _COV_FILE.parents[1]
    _ROOT_COV_FILES_AND_FOLDERS = [i for i in _COV_SITE_PACKAGES.iterdir() if i.name.startswith("coverage")]
    _SUBPROCESS_TRIGGER_PTH_NAME = "coverage-virtual-sub.pth"

    def __init__(self, link):
        self.link = link
        self.targets = []
        self.cov_pth = self._COV_SITE_PACKAGES / self._SUBPROCESS_TRIGGER_PTH_NAME

    def __enter__(self, creator):
        assert not self.cov_pth.exists()
        site_packages = creator.purelib
        p_th = site_packages / self._SUBPROCESS_TRIGGER_PTH_NAME

        if not str(p_th).startswith(str(self._COV_SITE_PACKAGES)):
            p_th.write_text("import coverage; coverage.process_startup()")
            self.targets.append((p_th, p_th.unlink))
            for entry in self._ROOT_COV_FILES_AND_FOLDERS:
                target = site_packages / entry.name
                if not target.exists():
                    clean = self.link(entry, target)
                    self.targets.append((target, clean))
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        assert self._COV_FILE.exists()
        for target, clean in self.targets:
            if target.exists():
                clean()
        assert not self.cov_pth.exists()
        assert self._COV_FILE.exists()


@pytest.fixture(scope="session")
def is_inside_ci():
    yield bool(os.environ.get(str("CI_RUN")))


@pytest.fixture(scope="session")
def special_char_name():
    base = "e-$ èрт🚒♞中片-j"
    # workaround for pypy3 https://bitbucket.org/pypy/pypy/issues/3147/venv-non-ascii-support-windows
    encoding = "ascii" if IS_PYPY and IS_WIN else sys.getfilesystemencoding()
    # let's not include characters that the file system cannot encode)
    result = ""
    for char in base:
        try:
            trip = char.encode(encoding, errors="strict").decode(encoding)
            if char == trip:
                result += char
        except ValueError:
            continue
    assert result
    return result


@pytest.fixture()
def special_name_dir(tmp_path, special_char_name):
    dest = Path(str(tmp_path)) / special_char_name
    yield dest
    if six.PY2 and sys.platform == "win32" and not IS_PYPY:  # pytest python2 windows does not support unicode delete
        shutil.rmtree(six.ensure_text(str(dest)))


@pytest.fixture(scope="session")
def current_creators():
    return PythonInfo.current_system().creators()


@pytest.fixture(scope="session")
def current_fastest(current_creators):
    return "builtin" if "builtin" in current_creators.key_to_class else next(iter(current_creators.key_to_class))
