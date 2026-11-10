from __future__ import annotations

import subprocess
from shlex import quote
from typing import TYPE_CHECKING, Final, NamedTuple

if TYPE_CHECKING:
    from collections.abc import Mapping

#: Process creation flag that hides the console window on Windows.
CREATE_NO_WINDOW: Final[int] = 0x80000000


class LogCmd:
    """Command line and environment, for logging the command that runs.

    :param cmd: the command and its arguments
    :param env: the environment the command runs with, ``None`` to inherit it

    """

    def __init__(self, cmd: list[str], env: Mapping[str, str] | None = None) -> None:
        self.cmd = cmd
        self.env = env

    def __repr__(self) -> str:
        cmd_repr = " ".join(quote(str(c)) for c in self.cmd)
        if self.env is not None:
            cmd_repr = f"{cmd_repr} env of {self.env!r}"
        return cmd_repr


def run_cmd(cmd: list[str], env: Mapping[str, str] | None = None) -> CmdResult:
    """Run a command and collect its exit code and output.

    :param cmd: the command and its arguments
    :param env: the environment the command runs with, ``None`` to inherit it

    :returns: the exit code, standard output and standard error

    """
    try:
        process = subprocess.Popen(
            cmd,
            universal_newlines=True,
            stdin=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stdout=subprocess.PIPE,
            encoding="utf-8",
            env=env,
        )
        out, err = process.communicate()  # input disabled
        code = process.returncode
    except OSError as error:
        code, out, err = error.errno, "", error.strerror
        # errno 2 is ENOENT, the missing executable case on every platform
        if code == 2 and err is not None and "file" in err:  # ruff:ignore[magic-value-comparison]
            err = str(error)  # FileNotFoundError in Python >= 3.3
    # errno and strerror are optional on OSError, so the tuple is not all str
    return CmdResult(code, out, err)  # ty: ignore[invalid-argument-type]


class CmdResult(NamedTuple):
    """Exit code and output of a command run by :func:`run_cmd`.

    :param code: the exit code of the command
    :param out: the standard output of the command
    :param err: the standard error of the command

    """

    code: int
    out: str
    err: str


__all__ = [
    "CREATE_NO_WINDOW",
    "CmdResult",
    "LogCmd",
    "run_cmd",
]
