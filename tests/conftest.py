# -*- coding: utf-8 -*-
from __future__ import absolute_import, unicode_literals

import logging
import os
import shutil
import sys
from contextlib import contextmanager
from functools import partial

import pytest
import six

from virtualenv.app_data import AppDataDiskFolder
from virtualenv.discovery.builtin import get_interpreter
from virtualenv.discovery.py_info import PythonInfo
from virtualenv.info import IS_PYPY, IS_WIN, fs_supports_symlink
from virtualenv.report import LOGGER
from virtualenv.util.path import Path
from virtualenv.util.six import ensure_str, ensure_text


def pytest_addoption(parser):
    parser.addoption("--int", action="store_true", default=False, help="run integration tests")


def pytest_configure(config):
    """Ensure randomly is called before we re-order"""
    manager = config.pluginmanager
    # noinspection PyProtectedMember
    order = manager.hook.pytest_collection_modifyitems._nonwrappers
    dest = next((i for i, p in enumerate(order) if p.plugin is manager.getplugin("randomly")), None)
    if dest is not None:
        from_pos = next(i for i, p in enumerate(order) if p.plugin is manager.getplugin(__file__))
        temp = order[dest]
        order[dest] = order[from_pos]
        order[from_pos] = temp


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
def ensure_py_info_cache_empty(session_app_data):
    PythonInfo.clear_cache(session_app_data)
    yield
    PythonInfo.clear_cache(session_app_data)


@contextmanager
def change_os_environ(key, value):
    env_var = key
    previous = os.environ[env_var] if env_var in os.environ else None
    os.environ[env_var] = value
    try:
        yield
    finally:
        if previous is not None:
            os.environ[env_var] = previous


@pytest.fixture(autouse=True, scope="session")
def ignore_global_config(tmp_path_factory):
    filename = str(tmp_path_factory.mktemp("folder") / "virtualenv-test-suite.ini")
    with change_os_environ(ensure_str("VIRTUALENV_CONFIG_FILE"), filename):
        yield


@pytest.fixture(autouse=True, scope="session")
def pip_cert(tmp_path_factory):
    # workaround for https://github.com/pypa/pip/issues/8984 - if the certificate is explicitly set no error can happen
    key = ensure_str("PIP_CERT")
    if key in os.environ:
        yield
    else:
        cert = tmp_path_factory.mktemp("folder") / "cert"
        import pkgutil

        cert_data = pkgutil.get_data("pip._vendor.certifi", "cacert.pem")
        cert.write_bytes(cert_data)
        with change_os_environ(key, str(cert)):
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
    override = {
        "VIRTUALENV_NO_PERIODIC_UPDATE": "1",
        "VIRTUALENV_NO_DOWNLOAD": "1",
    }
    for key, value in override.items():
        os.environ[str(key)] = str(value)
    is_exception = False
    try:
        yield
    except BaseException:
        is_exception = True
        raise
    finally:
        try:
            for key in override.keys():
                del os.environ[str(key)]
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
def coverage_env(monkeypatch, link, request):
    """
    Enable coverage report collection on the created virtual environments by injecting the coverage project
    """
    if COVERAGE_RUN and "no_coverage" not in request.fixturenames:
        # we inject right after creation, we cannot collect coverage on site.py - used for helper scripts, such as debug
        from virtualenv import run

        def _session_via_cli(args, options, setup_logging, env=None):
            session = prev_run(args, options, setup_logging, env)
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
        monkeypatch.setattr(run, "session_via_cli", _session_via_cli)

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


# no_coverage tells coverage_env to disable coverage injection for no_coverage user.
@pytest.fixture
def no_coverage():
    pass


if COVERAGE_RUN:
    import coverage

    class EnableCoverage(object):
        _COV_FILE = Path(coverage.__file__)
        _ROOT_COV_FILES_AND_FOLDERS = [i for i in _COV_FILE.parents[1].iterdir() if i.name.startswith("coverage")]

        def __init__(self, link):
            self.link = link
            self.targets = []

        def __enter__(self, creator):
            site_packages = creator.purelib
            for entry in self._ROOT_COV_FILES_AND_FOLDERS:
                target = site_packages / entry.name
                if not target.exists():
                    clean = self.link(entry, target)
                    self.targets.append((target, clean))
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            for target, clean in self.targets:
                if target.exists():
                    clean()
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
        shutil.rmtree(ensure_text(str(dest)))


@pytest.fixture(scope="session")
def current_creators(session_app_data):
    return PythonInfo.current_system(session_app_data).creators()


@pytest.fixture(scope="session")
def current_fastest(current_creators):
    return "builtin" if "builtin" in current_creators.key_to_class else next(iter(current_creators.key_to_class))


@pytest.fixture(scope="session")
def session_app_data(tmp_path_factory):
    temp_folder = tmp_path_factory.mktemp("session-app-data")
    app_data = AppDataDiskFolder(folder=str(temp_folder))
    with change_env_var(str("VIRTUALENV_OVERRIDE_APP_DATA"), str(app_data.lock.path)):
        yield app_data


@contextmanager
def change_env_var(key, value):
    """Temporarily change an environment variable.
    :param key: the key of the env var
    :param value: the value of the env var
    """
    already_set = key in os.environ
    prev_value = os.environ.get(key)
    os.environ[key] = value
    try:
        yield
    finally:
        if already_set:
            os.environ[key] = prev_value  # type: ignore
        else:
            del os.environ[key]  # pragma: no cover


@pytest.fixture()
def temp_app_data(monkeypatch, tmp_path):
    app_data = tmp_path / "app-data"
    monkeypatch.setenv(str("VIRTUALENV_OVERRIDE_APP_DATA"), str(app_data))
    return app_data


@pytest.fixture(scope="session")
def cross_python(is_inside_ci, session_app_data):
    spec = str(2 if sys.version_info[0] == 3 else 3)
    interpreter = get_interpreter(spec, [], session_app_data)
    if interpreter is None:
        msg = "could not find {}".format(spec)
        if is_inside_ci:
            raise RuntimeError(msg)
        pytest.skip(msg=msg)
    yield interpreter


@pytest.fixture(scope="session")
def for_py_version():
    return "{}.{}".format(*sys.version_info[0:2])


@pytest.fixture()
def skip_if_test_in_system(session_app_data):
    current = PythonInfo.current(session_app_data)
    if current.system_executable is not None:
        pytest.skip("test not valid if run under system")
