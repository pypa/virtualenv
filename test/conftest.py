from __future__ import absolute_import, unicode_literals

import os
from contextlib import contextmanager

import coverage
import pytest
from pathlib2 import Path

from virtualenv.util import symlink


@pytest.fixture(autouse=True)
def check_cwd_not_changed_by_test():
    old = os.getcwd()
    yield
    new = os.getcwd()
    if old != new:
        pytest.fail("test changed cwd: {!r} => {!r}".format(old, new))


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
                    msg = "test changed environ"
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
COV_FOLDERS = (
    [i for i in Path(coverage.__file__).parents[1].iterdir() if i.name.startswith("coverage")] if COVERAGE_RUN else None
)


@pytest.fixture(autouse=True)
def enable_coverage_in_virtual_env():
    """
    Enable coverage report collection on the created virtual environments by injecting the coverage project
    """
    if COVERAGE_RUN:
        # we inject right after creation, we cannot collect coverage on site.py - used for helper scripts, such as debug
        from virtualenv import run

        @contextmanager
        def post_perform(func, callback):
            _original = getattr(run, func)

            def internal(*args, **kwargs):
                try:
                    return _original(*args, **kwargs)
                finally:
                    callback(*args, **kwargs)  # now inject coverage tools

            try:
                setattr(run, func, internal)
                yield
            finally:
                setattr(run, func, _original)

        cov = EnableCoverage()
        with post_perform("_run_create", lambda c: cov.__enter__(c)):
            with post_perform("_run_via_cli", lambda a: cov.__exit__(None, None, None)):
                yield
    else:
        yield


class EnableCoverage(object):
    def __init__(self):
        self.targets = []

    def __enter__(self, creator):
        site_packages = creator.site_packages[0]
        for folder in COV_FOLDERS:
            target = site_packages / folder.name
            if not target.exists():
                symlink(folder, target)
            self.targets.append(target)
        p_th = site_packages / "coverage-virtualenv.pth"
        p_th.write_text("import coverage; coverage.process_startup()")
        self.targets.append(p_th)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        for target in self.targets:
            if target.exists():
                target.unlink()
