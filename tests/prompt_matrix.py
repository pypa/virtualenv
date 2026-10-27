"""Prompt payloads, the shell states that change how a stored prompt is read, and one driver for every activator."""

from __future__ import annotations

import os
import re
import shlex
import shutil
import subprocess
from argparse import Namespace
from typing import TYPE_CHECKING, Final, NamedTuple
from unittest.mock import create_autospec

from python_discovery import PythonInfo

from virtualenv.activation import (
    BashActivator,
    BatchActivator,
    CShellActivator,
    FishActivator,
    NushellActivator,
    PowerShellActivator,
    XonshActivator,
)
from virtualenv.create.creator import Creator
from virtualenv.info import IS_WIN

if TYPE_CHECKING:
    from pathlib import Path


class Shell(NamedTuple):
    activator: str
    script: str
    program: str
    states: dict[str, str]
    actions: dict[str, str]
    payloads: dict[str, str]


PROMPT_PAYLOADS: Final = {
    "command-substitution": "x$(touch PWNED)y",
    "backticks": "x`touch PWNED`y",
    "parameter-expansion": "x${$(touch PWNED)}y",
    "backslash-dollar": "x\\$(touch PWNED)y",
    "two-backslashes-dollar": "x\\\\$(touch PWNED)y",
    "three-backslashes-dollar": "x\\\\\\$(touch PWNED)y",
    "backslash-backtick": "x\\`touch PWNED`y",
    "quote-breakout": "x'$(touch PWNED)'y",
    "fish-backslash-quote": "x\\'$(touch PWNED)'\\'",
    "statement-separator": "a;touch PWNED;b",
    "placeholder": "A__VIRTUAL_NAME__B$(touch PWNED)",
    "history": "x!!y",
    "percent": "x%ny",
    "trailing-backslash": "e\\",
}

SHELLS: Final = {
    "bash": Shell(
        "bash",
        "activate",
        "bash",
        {
            "default": "",
            "promptvars-off": "shopt -u promptvars",
            "posix": "set -o posix",
            "compat42": "BASH_COMPAT=42",
            "compat42-promptvars-off": "BASH_COMPAT=42; shopt -u promptvars",
            "patsub-off": "shopt -u patsub_replacement",
            "compat42-patsub-off": "BASH_COMPAT=42; shopt -u patsub_replacement",
            "nounset": "set -u",
        },
        {
            "none": "",
            "promptvars-on": "shopt -s promptvars",
            "promptvars-off": "shopt -u promptvars",
            "posix": "set -o posix",
            "nounset-unset": "set -u; unset VIRTUAL_ENV_PROMPT",
            "child-bash": "export PS1; bash --noprofile --norc -i <<<exit 2>/dev/null",
            "child-dash": "export PS1; dash -i <<<exit 2>/dev/null",
            "child-zsh": "export PS1; zsh -f -i <<<exit 2>/dev/null",
        },
        PROMPT_PAYLOADS,
    ),
    "zsh": Shell(
        "bash",
        "activate",
        "zsh",
        {"default": "", "prompt-subst": "setopt prompt_subst"},
        {
            "none": "",
            "prompt-subst-on": "setopt prompt_subst",
            "prompt-subst-off": "unsetopt prompt_subst",
            "promptbang": "setopt promptbang",
            "emulate-sh": "emulate sh",
            "child-bash": "export PS1; bash --noprofile --norc -i <<<exit 2>/dev/null",
        },
        PROMPT_PAYLOADS,
    ),
    "fish": Shell(
        "fish",
        "activate.fish",
        "fish",
        {"default": ""},
        {"none": "fish_prompt", "child": "fish --no-config -c fish_prompt"},
        PROMPT_PAYLOADS,
    ),
    "cshell": Shell(
        "cshell",
        "activate.csh",
        "tcsh",
        {"default": "", "backslash-quote": "set backslash_quote"},
        {
            "none": "",
            "histchars": "set histchars = '#^'",
            "promptchars": "set promptchars = 'XY'",
            "unset-histchars": "unset histchars",
        },
        PROMPT_PAYLOADS,
    ),
    "nushell": Shell(
        "nushell",
        "activate.nu",
        "nu",
        {"default": ""},
        {
            "none": "print $env.VIRTUAL_ENV_PROMPT",
            "prompt-command": "print (do $env.PROMPT_COMMAND)",
            "child": "nu -n -c 'print $env.VIRTUAL_ENV_PROMPT'",
        },
        PROMPT_PAYLOADS | {"nu-marker": "x(touch PWNED)y"},
    ),
    "powershell": Shell(
        "powershell",
        "activate.ps1",
        "pwsh" if shutil.which("pwsh") else "powershell",
        {"default": ""},
        {
            "none": "prompt",
            "prompt-twice": "prompt; prompt",
            "child": "pwsh -NoProfile -NonInteractive -Command prompt",
        },
        PROMPT_PAYLOADS | {"pwsh-marker": "x$(New-Item PWNED)y"},
    ),
    "xonsh": Shell(
        "xonsh",
        "activate.xsh",
        "xonsh",
        {"default": ""},
        {
            "none": 'echo @("(" + $VIRTUAL_ENV_PROMPT + ") ")',
            "child": "print($(xonsh --no-rc -c 'import os; print(os.environ[\"VIRTUAL_ENV_PROMPT\"])'), end='')",
        },
        PROMPT_PAYLOADS | {"xonsh-marker": "x@(touch PWNED)y", "xonsh-color": "{RED}x"},
    ),
    "batch": Shell(
        "batch",
        "activate.bat",
        "cmd",
        {"default": "", "delayed-expansion": "/V:ON"},
        {
            "none": 'echo "%PROMPT:$$=$%"',
            "delayed-echo": 'setlocal enabledelayedexpansion & echo "%PROMPT:$$=$%"',
            "child": 'cmd /d /c echo "%PROMPT:$$=$%"',
        },
        PROMPT_PAYLOADS | {"cmd-marker": "x&type nul > PWNED&y"},
    ),
}

PROMPT_CASES: Final = [
    (shell, state, action, payload)
    for shell, spec in SHELLS.items()
    for state in spec.states
    for action in spec.actions
    for payload in spec.payloads
]


def unavailable(shell: str, action: str) -> str | None:
    """Why the shell, or the child shell the action starts, cannot run here; None when both can."""
    if shell not in {"nushell", "powershell"} and (shell == "batch") != IS_WIN:
        return f"{shell} activation needs {'Windows' if shell == 'batch' else 'a POSIX system'}"
    child: Final = action.removeprefix("child-") if action.startswith("child-") else None
    for program in (SHELLS[shell].program, child):
        if program is not None and shutil.which(program) is None:
            return f"{program} is not installed"
    return None


def generate_script(shell: str, root: Path, prompt: str) -> Path:
    """Render the shell's activation script in process; the scripts depend on the prompt, not on a real interpreter."""
    activator: Final = {
        "bash": BashActivator,
        "zsh": BashActivator,
        "fish": FishActivator,
        "cshell": CShellActivator,
        "nushell": NushellActivator,
        "powershell": PowerShellActivator,
        "xonsh": XonshActivator,
        "batch": BatchActivator,
    }[shell]
    creator: Final = create_autospec(
        Creator,
        instance=True,
        dest=root,
        bin_dir=root / "bin",
        interpreter=create_autospec(PythonInfo, instance=True, tcl_lib=None, tk_lib=None),
        pyenv_cfg={},
        env_name="env",
    )
    creator.bin_dir.mkdir(parents=True)
    activator(Namespace(prompt=prompt)).generate(creator)
    return creator.bin_dir / SHELLS[shell].script


def run_prompt(shell: str, script: Path, state: str, action: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    """Activate under the state, apply the later action, and draw the prompt the way that shell does."""
    spec: Final = SHELLS[shell]
    before: Final = spec.states[state]
    after: Final = spec.actions[action]
    stdin = ""
    env: dict[str, str] | None = None
    if shell in {"bash", "zsh"}:
        # interactive shells draw PS1 before each command they read, so the last draw follows the later action; child
        # shells an action starts still draw the inherited prompt, into /dev/null, so it cannot mix with the parent's
        argv = [spec.program, "--noprofile", "--norc", "-i"] if shell == "bash" else [spec.program, "-f", "-i"]
        stdin = f"{before}\nPS1=__END__\n. {shlex.quote(str(script))}\n{after}\nexit\n"
    elif shell == "cshell":
        argv = [spec.program, "-f", "-i"]
        stdin = f"{before}\nset prompt = __END__\nsource {script}\n{after}\nexit\n"
    elif shell == "fish":
        argv = [spec.program, "--no-config", "-c", f"source $argv[1]; {after}", str(script)]
    elif shell == "nushell":
        argv = [spec.program, "-n", "-c", f"overlay use '{script}'; {after}"]
    elif shell == "powershell":
        argv = [
            spec.program,
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            f"[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new(); . '{script}'; {after}",
        ]
    elif shell == "xonsh":
        argv = [spec.program, "--no-rc", "-c", f"source {shlex.quote(str(script))}\n{after}\n"]
        env = {k: v for k, v in os.environ.items() if k not in {"PYTHONHOME", "PYTHONWARNDEFAULTENCODING"}} | {
            "XONTRIBS_AUTOLOAD_DISABLED": "1",
            "XONSH_SHOW_TRACEBACK": "1",
        }
    else:
        (runner := cwd / "run.bat").write_text(f'@echo off\r\ncall "{script}"\r\n{after}\r\n', encoding="utf-8")
        argv = [spec.program, "/d", *before.split(), "/c", str(runner)]
    # an empty stdin keeps a child shell from waiting on the test runner's input
    return subprocess.run(
        argv,
        input=stdin,
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        timeout=120,
    )


def drawn_prompt(shell: str, result: subprocess.CompletedProcess[str]) -> str:
    """The last prompt an interactive bash, zsh or tcsh drew, up to the __END__ sentinel."""
    output: Final = result.stdout if shell == "cshell" else result.stderr
    last: Final = output.rsplit("__END__", 1)[0].rsplit("\n", 1)[-1]
    return (last.rsplit("> ", 1)[-1] if shell == "cshell" else last) + "__END__"


def prompt_shown(shell: str, result: subprocess.CompletedProcess[str], prompt: str, state: str, action: str) -> bool:
    """Whether the shell showed the prompt the way its display rule says."""
    if shell in {"bash", "zsh", "cshell"}:
        pattern: Final = _drawn_pattern(shell, prompt, state, action)
        return re.fullmatch(rf"\({pattern}\) __END__", drawn_prompt(shell, result)) is not None
    if shell == "nushell":
        return result.stdout.splitlines()[-1:] == [f"({prompt}) " if action == "prompt-command" else prompt]
    return _printed_text(shell, prompt, action) in result.stdout


def _drawn_pattern(shell: str, prompt: str, state: str, action: str) -> str:
    if shell != "bash":
        # zsh inserts the psvar entry and tcsh the escaped literal as data under every prompt option
        return re.escape(prompt)
    promptvars: Final = {"promptvars-on": True, "promptvars-off": False}.get(action, "promptvars-off" not in state)
    if "posix" in {state, action}:
        # posix mode draws !! as ! and a lone ! as the history number
        return "!".join(r"\d+".join(map(re.escape, piece.split("!"))) for piece in prompt.split("!!"))
    # without promptvars only the escape-decoding pass runs, so the escapes for the expansion pass stay visible
    return re.escape(prompt if promptvars else prompt.replace("\\", "\\\\").replace("`", "\\`"))


def _printed_text(shell: str, prompt: str, action: str) -> str:
    if shell == "xonsh":
        return f"({prompt}) " if action == "none" else prompt
    if shell == "batch":
        # the activator replaces the cmd.exe operators it cannot quote with spaces
        replaced: Final = re.sub(r'["&|<>^!]', " ", prompt)
        return f"({replaced}) "
    # a child fish or PowerShell does not run the activation script, so only the marker check applies to it
    return "" if action == "child" else f"({prompt}) "


__all__ = [
    "PROMPT_CASES",
    "PROMPT_PAYLOADS",
    "SHELLS",
    "drawn_prompt",
    "generate_script",
    "prompt_shown",
    "run_prompt",
    "unavailable",
]
