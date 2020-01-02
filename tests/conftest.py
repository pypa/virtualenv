# -*- coding: utf-8 -*-
from __future__ import absolute_import, unicode_literals

import os
import shutil
import sys
from functools import partial

import coverage
import pytest
import six

from virtualenv.interpreters.discovery.py_info import PythonInfo
from virtualenv.util import Path


@pytest.fixture(scope="session")
def has_symlink_support(tmp_path_factory):
    platform_supports = hasattr(os, "symlink")
    if platform_supports and sys.platform == "win32":
        # on Windows correct functioning of this is tied to SeCreateSymbolicLinkPrivilege, try if it works
        test_folder = tmp_path_factory.mktemp("symlink-tests")
        src = test_folder / "src"
        try:
            src.symlink_to(test_folder / "dest")
        except OSError:
            return False
        finally:
            shutil.rmtree(str(test_folder))

    return platform_supports


@pytest.fixture(scope="session")
def link_folder(has_symlink_support):
    if has_symlink_support:
        return os.symlink
    elif sys.platform == "win32" and sys.version_info[0:2] > (3, 4):
        # on Windows junctions may be used instead
        import _winapi  # python3.5 has builtin implementation for junctions

        return _winapi.CreateJunction
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
def check_cwd_not_changed_by_test():
    old = os.getcwd()
    yield
    new = os.getcwd()
    if old != new:
        pytest.fail("tests changed cwd: {!r} => {!r}".format(old, new))


@pytest.fixture(autouse=True)
def ensure_py_info_cache_empty():
    yield
    PythonInfo._cache_from_exe.clear()


@pytest.fixture(autouse=True)
def clean_data_dir(tmp_path, monkeypatch):
    from virtualenv import info

    monkeypatch.setattr(info, "_DATA_DIR", tmp_path)
    yield


@pytest.fixture(autouse=True)
def check_os_environ_stable():
    old = os.environ.copy()
    # ensure we don't inherit parent env variables
    to_clean = {
        k for k in os.environ.keys() if k.startswith("VIRTUALENV_") or "VIRTUAL_ENV" in k or k.startswith("TOX_")
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
                    if old[k] != new[k] and not k.startswith("PYTEST_")
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
COVERAGE_RUN = os.environ.get(COV_ENV_VAR)


@pytest.fixture(autouse=True)
def coverage_env(monkeypatch, link):
    """
    Enable coverage report collection on the created virtual environments by injecting the coverage project
    """
    if COVERAGE_RUN:
        # we inject right after creation, we cannot collect coverage on site.py - used for helper scripts, such as debug
        from virtualenv import run

        def via_cli(args):
            session = prev_run(args)
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
        site_packages = creator.site_packages[0]
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
    yield "CI_RUN" in os.environ


@pytest.fixture(scope="session")
def special_char_name():
    base = "$ èрт🚒♞中片"
    encoding = sys.getfilesystemencoding()
    # let's not include characters that the file system cannot encode)
    result = ""
    for char in base:
        try:
            encoded = char.encode(encoding, errors="strict")
            if char == "?" or encoded != b"?":  # mbcs notably on Python 2 uses replace even for strict
                result += char
        except ValueError:
            continue
    assert result
    return result


@pytest.fixture()
def special_name_dir(tmp_path, special_char_name):
    dest = Path(str(tmp_path)) / special_char_name
    yield dest
    if six.PY2 and sys.platform == "win32":  # pytest python2 windows does not support unicode delete
        shutil.rmtree(six.ensure_text(str(dest)))
