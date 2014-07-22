#!/usr/bin/env python
"""
Helper script to rebuild virtualenv.py from virtualenv_support
"""

import re
import os
import sys
import base64
import zlib

here = os.path.dirname(__file__)
script = os.path.join(here, '..', 'virtualenv.py')

file_regex = re.compile(
    b'##file (.*?)\n([a-zA-Z][a-zA-Z0-9_]+)\\s*=\\s*convert\\("""(.*?)"""\\)',
    re.S)
file_template = '##file %(filename)s\n%(varname)s = convert("""\n%(data)s""")'

def rebuild():
    f = open(script, 'rb')
    content = f.read()
    f.close()
    parts = []
    last_pos = 0
    match = None
    for match in file_regex.finditer(content):
        parts.append(content[last_pos:match.start()])
        last_pos = match.end()
        filename = match.group(1).decode('utf-8')
        varname = match.group(2).decode('utf-8')
        data = match.group(3)
        print('Found reference to file %s' % filename)
        pathname = os.path.join(here, '..', 'virtualenv_embedded', filename)
        f = open(pathname, 'rb')
        c = f.read()
        f.close()
        new_data = base64.encodestring(zlib.compress(c))
        if new_data.strip() == data.strip():
            print('  Reference up to date (%s bytes)' % len(c))
            parts.append(match.group(0))
            continue
        print('  Content changed (%s bytes -> %s bytes)' % (
            zipped_len(data), len(c)))
        new_match = file_template % dict(
            filename=filename,
            varname=varname,
            data=new_data.decode('utf-8'))
        parts.append(new_match.encode('utf-8'))
    parts.append(content[last_pos:])
    new_content = b''.join(parts)
    if new_content != content:
        sys.stdout.write('Content updated; overwriting... ')
        f = open(script, 'wb')
        f.write(new_content)
        f.close()
        print('done.')
    else:
        print('No changes in content')
    if match is None:
        print('No variables were matched/found')

def zipped_len(data):
    if not data:
        return 'no data'
    try:
        return len(zlib.decompress(base64.decodestring(data)))
    except:
        return 'unknown'

if __name__ == '__main__':
    rebuild()
    
