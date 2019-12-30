import sys

import six

if six.PY3:
    from pathlib import Path

    if sys.version_info[0:2] == (3, 4):
        BuiltinPath = Path

        class Path(type(BuiltinPath())):
            def read_text(self, encoding=None, errors=None):
                """
                Open the file in text mode, read it, and close the file.
                """
                with self.open(mode="r", encoding=encoding, errors=errors) as f:
                    return f.read()

            def write_text(self, data, encoding=None, errors=None):
                """
                Open the file in text mode, write to it, and close the file.
                """
                if not isinstance(data, str):
                    raise TypeError("data must be str, not %s" % data.__class__.__name__)
                with self.open(mode="w", encoding=encoding, errors=errors) as f:
                    return f.write(data)


else:
    from pathlib2 import Path

    if sys.platform == "win32":
        # workaround for https://github.com/mcmtroffaes/pathlib2/issues/56
        sys.modules["pathlib2"].sys.getfilesystemencoding = lambda: "utf-8"

__all__ = ("Path",)
