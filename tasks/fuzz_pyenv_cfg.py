"""Fuzz the pyvenv.cfg writer and reader for configuration injection.

This asserts the same invariant as tests/property/test_pyenv_cfg.py, with a coverage-guided driver rather than
hypothesis: a value must never be read back as an extra configuration key. That is the property that #3247 violated,
where a prompt containing a line boundary could override ``home``.

Run directly: python tasks/fuzz_pyenv_cfg.py -runs=100000

"""

from __future__ import annotations

import sys
import tempfile
from collections import OrderedDict
from pathlib import Path

import atheris

with atheris.instrument_imports(include=["virtualenv"]):
    from virtualenv.create.pyenv_cfg import PyEnvCfg


@atheris.instrument_func
def test_one_input(data: bytes) -> None:
    provider = atheris.FuzzedDataProvider(data)
    keys = ("home", "prompt", "version", "base-prefix")
    content = OrderedDict(
        (keys[i], provider.ConsumeUnicodeNoSurrogates(provider.remaining_bytes() // (len(keys) - i or 1)))
        for i in range(len(keys))
    )
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / "pyvenv.cfg"
        PyEnvCfg(content, path).write()
        read_back = PyEnvCfg.from_file(path).content
    extra = set(read_back) - set(content)
    assert not extra, (extra, dict(content))  # ruff:ignore[assert] atheris treats AssertionError as the crash signal


if __name__ == "__main__":
    atheris.Setup(sys.argv, test_one_input)
    atheris.Fuzz()
