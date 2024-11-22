"""Helper script to rebuild virtualenv.py from virtualenv_support."""  # noqa: EXE002

from __future__ import annotations

import codecs
import locale
import os
import re
from zlib import crc32 as _crc32


def crc32(data):
    """Python version idempotent."""
    return _crc32(data.encode()) & 0xFFFFFFFF


here = os.path.realpath(os.path.dirname(__file__))
script = os.path.realpath(os.path.join(here, "..", "src", "virtualenv.py"))

gzip = codecs.lookup("zlib")
b64 = codecs.lookup("base64")

file_regex = re.compile(r'# file (.*?)\n([a-zA-Z][a-zA-Z0-9_]+) = convert\(\n {4}"""\n(.*?)"""\n\)', re.DOTALL)
file_template = '# file {filename}\n{variable} = convert(\n    """\n{data}"""\n)'


def rebuild(script_path):
    with script_path.open(encoding=locale.getpreferredencoding(False)) as current_fh:  # noqa: FBT003
        script_content = current_fh.read()
    script_parts = []
    match_end = 0
    next_match = None
    _count, did_update = 0, False
    for _count, next_match in enumerate(file_regex.finditer(script_content)):
        script_parts += [script_content[match_end : next_match.start()]]
        match_end = next_match.end()
        filename, variable_name, previous_encoded = next_match.group(1), next_match.group(2), next_match.group(3)
        differ, content = handle_file(next_match.group(0), filename, variable_name, previous_encoded)
        script_parts.append(content)
        if differ:
            did_update = True

    script_parts += [script_content[match_end:]]
    new_content = "".join(script_parts)

    report(1 if not _count or did_update else 0, new_content, next_match, script_content, script_path)


def handle_file(previous_content, filename, variable_name, previous_encoded):
    print(f"Found file {filename}")  # noqa: T201
    current_path = os.path.realpath(os.path.join(here, "..", "src", "virtualenv_embedded", filename))
    _, file_type = os.path.splitext(current_path)
    keep_line_ending = file_type == ".bat"
    with open(current_path, encoding="utf-8", newline="" if keep_line_ending else None) as current_fh:
        current_text = current_fh.read()
    current_crc = crc32(current_text)
    current_encoded = b64.encode(gzip.encode(current_text.encode())[0])[0].decode()
    if current_encoded == previous_encoded:
        print(f"  File up to date (crc: {current_crc:08x})")  # noqa: T201
        return False, previous_content
    # Else: content has changed
    previous_text = gzip.decode(b64.decode(previous_encoded.encode())[0])[0].decode()
    previous_crc = crc32(previous_text)
    print(f"  Content changed (crc: {previous_crc:08x} -> {current_crc:08x})")  # noqa: T201
    new_part = file_template.format(filename=filename, variable=variable_name, data=current_encoded)
    return True, new_part


def report(exit_code, new, next_match, current, script_path):
    if new != current:
        print("Content updated; overwriting... ", end="")  # noqa: T201
        script_path.write_bytes(new)
        print("done.")  # noqa: T201
    else:
        print("No changes in content")  # noqa: T201
    if next_match is None:
        print("No variables were matched/found")  # noqa: T201
    raise SystemExit(exit_code)


if __name__ == "__main__":
    rebuild(script)
