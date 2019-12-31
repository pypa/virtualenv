import sys
from contextlib import contextmanager

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
        import os

        class Path(object):
            def __init__(self, path):
                self.path = six.ensure_text(path)

            def __div__(self, other):
                return Path(os.path.join(self.path, other.path if isinstance(other, Path) else six.ensure_text(other)))

            def exists(self):
                return os.path.exists(self.path)

            def absolute(self):
                return Path(os.path.abspath(self.path))

            @property
            def parent(self):
                return Path(os.path.abspath(os.path.join(self.path, os.path.pardir)))

            def resolve(self):
                return Path(os.path.realpath(self.path))

            @property
            def name(self):
                return os.path.basename(self.path)

            @property
            def parts(self):
                return self.path.split(os.sep)

            def is_file(self):
                return os.path.isfile(self.path)

            def is_dir(self):
                return os.path.isdir(self.path)

            def __repr__(self):
                return "Path({})".format(self.path)

            def __str__(self):
                return self.path.decode("utf-8")

            def mkdir(self, parents=True, exist_ok=True):
                if not self.exists() and exist_ok:
                    os.makedirs(self.path)

            def read_text(self, encoding="utf-8"):
                with open(self.path, "rb") as file_handler:
                    return file_handler.read().decode(encoding)

            def write_text(self, text, encoding="utf-8"):
                with open(self.path, "wb") as file_handler:
                    file_handler.write(text.encode(encoding))

            def iterdir(self):
                for p in os.listdir(self.path):
                    yield Path(os.path.join(self.path, p))

            @property
            def suffix(self):
                _, ext = os.path.splitext(self.name)
                return ext

            @property
            def stem(self):
                base, _ = os.path.splitext(self.name)
                return base

            @contextmanager
            def open(self):
                with open(self.path) as file_handler:
                    yield file_handler


__all__ = ("Path",)
