"""Inspect a target Python interpreter virtual environment wise"""
import sys  # built-in

PYPY2_WIN = hasattr(sys, "pypy_version_info") and sys.platform != "win32" and sys.version_info[0] == 2


def encode_path(value):
    if value is None:
        return None
    if not isinstance(value, (str, bytes)):
        if isinstance(value, type):
            value = repr(value)
        else:
            value = repr(type(value))
    if isinstance(value, bytes) and not PYPY2_WIN:
        value = value.decode(sys.getfilesystemencoding())
    return value


def encode_list_path(value):
    return [encode_path(i) for i in value]


def run():
    """print debug data about the virtual environment"""
    try:
        from collections import OrderedDict
    except ImportError:  # pragma: no cover
        # this is possible if the standard library cannot be accessed
        # noinspection PyPep8Naming
        OrderedDict = dict  # pragma: no cover
    result = OrderedDict([("sys", OrderedDict())])
    path_keys = (
        "executable",
        "_base_executable",
        "prefix",
        "base_prefix",
        "real_prefix",
        "exec_prefix",
        "base_exec_prefix",
        "path",
        "meta_path",
    )
    for key in path_keys:
        value = getattr(sys, key, None)
        if isinstance(value, list):
            value = encode_list_path(value)
        else:
            value = encode_path(value)
        result["sys"][key] = value
    result["sys"]["fs_encoding"] = sys.getfilesystemencoding()
    result["sys"]["io_encoding"] = getattr(sys.stdout, "encoding", None)
    result["version"] = sys.version
    import os  # landmark

    result["os"] = repr(os)

    try:
        # noinspection PyUnresolvedReferences
        import site  # site

        result["site"] = repr(site)
    except ImportError as exception:  # pragma: no cover
        result["site"] = repr(exception)  # pragma: no cover

    try:
        # noinspection PyUnresolvedReferences
        import datetime  # site

        result["datetime"] = repr(datetime)
    except ImportError as exception:  # pragma: no cover
        result["datetime"] = repr(exception)  # pragma: no cover

    try:
        # noinspection PyUnresolvedReferences
        import math  # site

        result["math"] = repr(math)
    except ImportError as exception:  # pragma: no cover
        result["math"] = repr(exception)  # pragma: no cover

    # try to print out, this will validate if other core modules are available (json in this case)
    try:
        import json

        result["json"] = repr(json)
        print(json.dumps(result, indent=2))
    except (ImportError, ValueError, TypeError) as exception:  # pragma: no cover
        result["json"] = repr(exception)  # pragma: no cover
        print(repr(result))  # pragma: no cover
        raise SystemExit(1)  # pragma: no cover


if __name__ == "__main__":
    run()
