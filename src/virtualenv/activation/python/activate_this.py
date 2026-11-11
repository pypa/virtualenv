"""Activate virtualenv for current interpreter:

import runpy runpy.run_path(this_file)

This can be used when you must use an existing Python interpreter, not the virtualenv bin/python.

"""  # ruff:ignore[missing-terminal-punctuation]  # the usage line is code, so the docstring needs no closing sentence

from __future__ import annotations

import os
import site
import sys

# runpy.run_path returns these globals; keep the names emitted by existing activation scripts.
try:
    abs_file = os.path.abspath(__file__)  # simplint: ignore[module-variable-case, module-variable-prefix, undocumented-public-api]  # runpy result  # fmt: skip
except NameError as exc:
    msg = "You must use import runpy; runpy.run_path(this_file)"  # simplint: ignore[undocumented-public-api]  # runpy result
    raise AssertionError(msg) from exc

bin_dir = os.path.dirname(abs_file)  # simplint: ignore[module-variable-case, module-variable-prefix, undocumented-public-api]  # runpy result  # fmt: skip
# __BIN_NAME__ is filled in when the script is written
base = bin_dir[: -len(__BIN_NAME__) - 1]  # ty: ignore[unresolved-reference]  # simplint: ignore[module-variable-case, module-variable-prefix, undocumented-public-api]  # runpy result

# Empty PATH entries search the current directory on POSIX.
os.environ["PATH"] = os.pathsep.join([
    bin_dir,
    *(entry for entry in os.environ.get("PATH", "").split(os.pathsep) if entry),
])
os.environ["VIRTUAL_ENV"] = base  # virtual env is right above bin directory
# __VIRTUAL_PROMPT__ is filled in when the script is written
os.environ["VIRTUAL_ENV_PROMPT"] = __VIRTUAL_PROMPT__ or os.path.basename(base)  # ty: ignore[unresolved-reference]
os.environ.pop("PYTHONHOME", None)

# Set PKG_CONFIG_PATH to include the virtualenv's pkgconfig directory
pkg_config_path = os.path.join(base, "lib", "pkgconfig")  # simplint: ignore[module-variable-case, module-variable-prefix, missing-final, undocumented-public-api]  # runpy result  # fmt: skip
if existing_pkg_config_path := os.environ.get("PKG_CONFIG_PATH", ""):
    os.environ["PKG_CONFIG_PATH"] = os.pathsep.join([pkg_config_path, existing_pkg_config_path])
else:
    os.environ["PKG_CONFIG_PATH"] = pkg_config_path

# add the virtual environments libraries to the host python import mechanism
prev_length = len(sys.path)  # simplint: ignore[module-variable-case, module-variable-prefix, missing-final, undocumented-public-api]  # runpy result  # fmt: skip
# __LIB_FOLDERS__ is filled in when the script is written
for lib in __LIB_FOLDERS__.split(os.pathsep):  # ty: ignore[unresolved-reference]
    path = os.path.realpath(os.path.join(bin_dir, lib))  # simplint: ignore[module-variable-case, module-variable-prefix]  # runpy result  # fmt: skip
    # __DECODE_PATH__ is filled in as an empty string, so the decode branch never runs
    site.addsitedir(path.decode("utf-8") if __DECODE_PATH__ else path)  # ty: ignore[unresolved-reference,missing-attribute]
sys.path[:] = sys.path[prev_length:] + sys.path[0:prev_length]

# sys.real_prefix is a legacy attribute that older tools read
sys.real_prefix = sys.prefix  # ty: ignore[missing-attribute]
sys.prefix = base
