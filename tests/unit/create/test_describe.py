from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from virtualenv.create.describe import Describe


def test_calc_config_vars_handles_non_string_values() -> None:
    interpreter = MagicMock()
    interpreter.prefix = "/usr"
    interpreter.sysconfig_vars = {
        "PYTHONFRAMEWORK": "",
        "Py_ENABLE_SHARED": 1,
        "LIBDIR": "/usr/lib",
        "INSTSONAME": "libpython3.14.so",
    }

    describe = MagicMock(spec=Describe)
    describe.interpreter = interpreter
    describe.dest = Path("/venv")

    result = Describe._calc_config_vars(describe, Path("/venv"))  # noqa: SLF001
    assert result["Py_ENABLE_SHARED"] == 1
    assert result["LIBDIR"] == Path("/venv")
    assert result["INSTSONAME"] == "libpython3.14.so"
