"""Inspect a target Python interpreter virtual environment wise"""
import sys  # built-in


def run():
    """print debug data about the virtual environment"""
    try:
        from collections import OrderedDict
    except ImportError:  # pragma: no cover
        # this is possible if the standard library cannot be accessed
        # noinspection PyPep8Naming
        OrderedDict = dict  # pragma: no cover
    result = OrderedDict([("sys", OrderedDict())])
    for key in (
        "executable",
        "_base_executable",
        "prefix",
        "base_prefix",
        "real_prefix",
        "exec_prefix",
        "base_exec_prefix",
        "path",
        "meta_path",
        "version",
    ):
        value = getattr(sys, key, None)
        if key == "meta_path" and value is not None:
            value = [repr(i) for i in value]
        result["sys"][key] = value

    import os  # landmark

    result["os"] = os.__file__

    try:
        # noinspection PyUnresolvedReferences
        import site  # site

        result["site"] = site.__file__
    except ImportError as exception:  # pragma: no cover
        result["site"] = repr(exception)  # pragma: no cover
    # try to print out, this will validate if other core modules are available (json in this case)
    try:
        import json

        result["json"] = repr(json)
        print(json.dumps(result, indent=2))
    except ImportError as exception:  # pragma: no cover
        result["json"] = repr(exception)  # pragma: no cover
        print(repr(result))  # pragma: no cover
        raise SystemExit(1)  # pragma: no cover


if __name__ == "__main__":
    run()
