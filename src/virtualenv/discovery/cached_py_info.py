"""

We acquire the python information by running an interrogation script via subprocess trigger. This operation is not
cheap, especially not on Windows. To not have to pay this hefty cost every time we apply multiple levels of
caching.
"""
from __future__ import absolute_import, unicode_literals

import json
import logging
import os
import pipes
import sys
from collections import OrderedDict
from hashlib import sha256

from virtualenv.discovery.py_info import PythonInfo
from virtualenv.info import PY2, PY3
from virtualenv.util.path import Path
from virtualenv.util.six import ensure_text
from virtualenv.util.subprocess import Popen, subprocess
from virtualenv.util.zipapp import ensure_file_on_disk
from virtualenv.version import __version__

_CACHE = OrderedDict()
_CACHE[Path(sys.executable)] = PythonInfo()


def from_exe(cls, app_data, exe, raise_on_error=True, ignore_cache=False):
    """"""
    py_info_cache = _get_py_info_cache(app_data)
    result = _get_from_cache(cls, py_info_cache, app_data, exe, ignore_cache=ignore_cache)
    if isinstance(result, Exception):
        if raise_on_error:
            raise result
        else:
            logging.info("%s", str(result))
        result = None
    return result


def _get_py_info_cache(app_data):
    return None if app_data is None else app_data / "py_info" / __version__


def _get_from_cache(cls, py_info_cache, app_data, exe, ignore_cache=True):
    # note here we cannot resolve symlinks, as the symlink may trigger different prefix information if there's a
    # pyenv.cfg somewhere alongside on python3.4+
    exe_path = Path(exe)
    if not ignore_cache and exe_path in _CACHE:  # check in the in-memory cache
        result = _CACHE[exe_path]
    elif py_info_cache is None:  # cache disabled
        failure, py_info = _run_subprocess(cls, exe, app_data)
        result = py_info if failure is None else failure
    else:  # then check the persisted cache
        py_info = _get_via_file_cache(cls, py_info_cache, app_data, exe_path, exe)
        result = _CACHE[exe_path] = py_info
    # independent if it was from the file or in-memory cache fix the original executable location
    if isinstance(result, PythonInfo):
        result.executable = exe
    return result


def _get_via_file_cache(cls, py_info_cache, app_data, resolved_path, exe):
    key = sha256(str(resolved_path).encode("utf-8") if PY3 else str(resolved_path)).hexdigest()
    py_info = None
    resolved_path_text = ensure_text(str(resolved_path))
    try:
        resolved_path_modified_timestamp = resolved_path.stat().st_mtime
    except OSError:
        resolved_path_modified_timestamp = -1
    data_file = py_info_cache / "{}.json".format(key)
    with py_info_cache.lock_for_key(key):
        data_file_path = data_file.path
        if data_file_path.exists() and resolved_path_modified_timestamp != 1:  # if exists and matches load
            try:
                data = json.loads(data_file_path.read_text())
                if data["path"] == resolved_path_text and data["st_mtime"] == resolved_path_modified_timestamp:
                    logging.debug("get PythonInfo from %s for %s", data_file_path, exe)
                    py_info = cls._from_dict({k: v for k, v in data["content"].items()})
                else:
                    raise ValueError("force close as stale")
            except (KeyError, ValueError, OSError):
                logging.debug("remove PythonInfo %s for %s", data_file_path, exe)
                data_file_path.unlink()  # close out of date files
        if py_info is None:  # if not loaded run and save
            failure, py_info = _run_subprocess(cls, exe, app_data)
            if failure is None:
                file_cache_content = {
                    "st_mtime": resolved_path_modified_timestamp,
                    "path": resolved_path_text,
                    "content": py_info._to_dict(),
                }
                logging.debug("write PythonInfo to %s for %s", data_file_path, exe)
                data_file_path.write_text(ensure_text(json.dumps(file_cache_content, indent=2)))
            else:
                py_info = failure
    return py_info


def _run_subprocess(cls, exe, app_data):
    resolved_path = Path(os.path.abspath(__file__)).parent / "py_info.py"
    with ensure_file_on_disk(resolved_path, app_data) as resolved_path:
        cmd = [exe, str(resolved_path)]
        # prevent sys.prefix from leaking into the child process - see https://bugs.python.org/issue22490
        env = os.environ.copy()
        env.pop("__PYVENV_LAUNCHER__", None)
        logging.debug("get interpreter info via cmd: %s", LogCmd(cmd))
        try:
            process = Popen(
                cmd,
                universal_newlines=True,
                stdin=subprocess.PIPE,
                stderr=subprocess.PIPE,
                stdout=subprocess.PIPE,
                env=env,
            )
            out, err = process.communicate()
            code = process.returncode
        except OSError as os_error:
            out, err, code = "", os_error.strerror, os_error.errno
    result, failure = None, None
    if code == 0:
        result = cls._from_json(out)
        result.executable = exe  # keep original executable as this may contain initialization code
    else:
        msg = "failed to query {} with code {}{}{}".format(
            exe, code, " out: {!r}".format(out) if out else "", " err: {!r}".format(err) if err else ""
        )
        failure = RuntimeError(msg)
    return failure, result


class LogCmd(object):
    def __init__(self, cmd, env=None):
        self.cmd = cmd
        self.env = env

    def __repr__(self):
        def e(v):
            return v.decode("utf-8") if isinstance(v, bytes) else v

        cmd_repr = e(" ").join(pipes.quote(e(c)) for c in self.cmd)
        if self.env is not None:
            cmd_repr += e(" env of {!r}").format(self.env)
        if PY2:
            return cmd_repr.encode("utf-8")
        return cmd_repr

    def __unicode__(self):
        raw = repr(self)
        if PY2:
            return raw.decode("utf-8")
        return raw


def clear(app_data):
    py_info_cache = _get_py_info_cache(app_data)
    if py_info_cache is not None:
        with py_info_cache:
            for filename in py_info_cache.path.iterdir():
                if filename.suffix == ".json":
                    with py_info_cache.lock_for_key(filename.stem):
                        if filename.exists():
                            filename.unlink()
    _CACHE.clear()


___all___ = (
    "from_exe",
    "clear",
    "LogCmd",
)
