"""Helper script to rebuild virtualenv.py from virtualenv_support."""

from __future__ import annotations

import codecs
import locale
import os
import re
from typing import TYPE_CHECKING, Final, NoReturn
from zlib import crc32 as _crc32

if TYPE_CHECKING:
    from pathlib import Path


def crc32(data: str) -> int:
    return _crc32(data.encode()) & 0xFFFFFFFF


here: Final[str] = os.path.realpath(os.path.dirname(__file__))
script: Final[str] = os.path.realpath(os.path.join(here, "..", "src", "virtualenv.py"))

_GZIP: Final[codecs.CodecInfo] = codecs.lookup("zlib")
_B64: Final[codecs.CodecInfo] = codecs.lookup("base64")

_FILE_REGEX: Final[re.Pattern[str]] = re.compile(
    r'# file (.*?)\n([a-zA-Z][a-zA-Z0-9_]+) = convert\(\n {4}"""\n(.*?)"""\n\)', re.DOTALL
)


def rebuild(script_path: Path) -> None:
    encoding = (
        locale.getencoding() if hasattr(locale, "getencoding") else locale.getpreferredencoding(do_setlocale=False)
    )
    with script_path.open(encoding=encoding) as current_fh:
        script_content = current_fh.read()
    script_parts = []
    match_end = 0
    next_match = None
    count, did_update = 0, False
    # count is unused, the loop needs only the match
    for count, next_match in enumerate(_FILE_REGEX.finditer(script_content)):  # ruff:ignore[unused-loop-control-variable]
        script_parts += [script_content[match_end : next_match.start()]]
        match_end = next_match.end()
        filename, variable_name, previous_encoded = next_match.group(1), next_match.group(2), next_match.group(3)
        differ, content = handle_file(next_match.group(0), filename, variable_name, previous_encoded)
        script_parts.append(content)
        if differ:
            did_update = True

    script_parts += [script_content[match_end:]]

    report(1 if not count or did_update else 0, "".join(script_parts), next_match, script_content, script_path)


def handle_file(previous_content: str, filename: str, variable_name: str, previous_encoded: str) -> tuple[bool, str]:
    print(f"Found file {filename}")  # ruff:ignore[print]  # the script reports each file it finds to the terminal
    current_path = os.path.realpath(os.path.join(here, "..", "src", "virtualenv_embedded", filename))
    _, file_type = os.path.splitext(current_path)
    with open(current_path, encoding="utf-8", newline="" if (file_type == ".bat") else None) as current_fh:
        current_text = current_fh.read()
    current_crc = crc32(current_text)
    current_encoded = _B64.encode(_GZIP.encode(current_text.encode())[0])[0].decode()
    if current_encoded == previous_encoded:
        # the script reports each file's status to the terminal
        print(f"  File up to date (crc: {current_crc:08x})")  # ruff:ignore[print]
        return False, previous_content
    # Else: content has changed
    previous_text = _GZIP.decode(_B64.decode(previous_encoded.encode())[0])[0].decode()
    # the script reports each file's status to the terminal
    print(f"  Content changed (crc: {crc32(previous_text):08x} -> {current_crc:08x})")  # ruff:ignore[print]
    file_template: str = '# file {filename}\n{variable} = convert(\n    """\n{data}"""\n)'
    return True, file_template.format(filename=filename, variable=variable_name, data=current_encoded)


def report(exit_code: int, new: str, next_match: re.Match[str] | None, current: str, script_path: Path) -> NoReturn:
    if new != current:
        # the script reports each file's status to the terminal
        print("Content updated; overwriting... ", end="")  # ruff:ignore[print]
        script_path.write_bytes(new)
        print("done.")  # ruff:ignore[print]  # the script reports each file's status to the terminal
    else:
        print("No changes in content")  # ruff:ignore[print]  # the script reports each file's status to the terminal
    if next_match is None:
        # the script reports each file's status to the terminal
        print("No variables were matched/found")  # ruff:ignore[print]
    raise SystemExit(exit_code)


if __name__ == "__main__":
    rebuild(script)
