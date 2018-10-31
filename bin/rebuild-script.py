#!/usr/bin/env python
"""
Helper script to rebuild virtualenv.py from virtualenv_support
"""
from __future__ import print_function

import codecs
import os
import re
from zlib import crc32 as _crc32


def crc32(data):
    """Python version idempotent"""
    return _crc32(data) & 0xFFFFFFFF


here = os.path.dirname(__file__)
script = os.path.join(here, "..", "src", "virtualenv.py")

gzip = codecs.lookup("zlib")
b64 = codecs.lookup("base64")

file_regex = re.compile(br'# file (.*?)\n([a-zA-Z][a-zA-Z0-9_]+) = convert\(\n    """\n(.*?)"""\n\)', re.S)
file_template = b'# file %(filename)s\n%(variable)s = convert(\n    """\n%(data)s"""\n)'


def rebuild(script_path):
    exit_code = 0
    with open(script_path, "rb") as f:
        script_content = f.read()
    parts = []
    last_pos = 0
    match = None
    _count = 0
    for _count, match in enumerate(file_regex.finditer(script_content)):
        parts += [script_content[last_pos : match.start()]]
        last_pos = match.end()
        filename, fn_decoded = match.group(1), match.group(1).decode()
        variable = match.group(2)
        data = match.group(3)

        print("Found file %s" % fn_decoded)
        pathname = os.path.join(here, "..", "virtualenv_embedded", fn_decoded)

        with open(pathname, "rb") as f:
            embedded = f.read()
        new_crc = crc32(embedded)
        new_data = b64.encode(gzip.encode(embedded)[0])[0]

        if new_data == data:
            print("  File up to date (crc: %08x)" % new_crc)
            parts += [match.group(0)]
            continue
        exit_code = 1
        # Else: content has changed
        crc = crc32(gzip.decode(b64.decode(data)[0])[0])
        print("  Content changed (crc: {:08x} -> {:08x})".format(crc, new_crc))
        new_match = file_template % {b"filename": filename, b"variable": variable, b"data": new_data}
        parts += [new_match]

    parts += [script_content[last_pos:]]
    new_content = b"".join(parts)

    if new_content != script_content:
        print("Content updated; overwriting... ", end="")
        with open(script_path, "wb") as f:
            f.write(new_content)
        print("done.")
    else:
        print("No changes in content")
    if match is None:
        print("No variables were matched/found")
    if not _count:
        exit_code = 1
    raise SystemExit(exit_code)


if __name__ == "__main__":
    rebuild(script)
