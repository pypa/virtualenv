import sys
from contextlib import contextmanager

import six

if six.PY3:
    from pathlib import Path

    if sys.version_info[0:2] == (3, 4):
        # no read/write text on python3.4
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
    if sys.platform == "win32":
        # workaround for https://github.com/mcmtroffaes/pathlib2/issues/56
        import os

        class Path(object):
            def __init__(self, path):
                self._path = path._path if isinstance(path, Path) else six.ensure_text(path)

            def __repr__(self):
                return six.ensure_str(u"Path({})".format(self._path))

            def __str__(self):
                return six.ensure_str(self._path)

            def __div__(self, other):
                return Path(
                    os.path.join(self._path, other._path if isinstance(other, Path) else six.ensure_text(other))
                )

            def __eq__(self, other):
                return self._path == (other._path if isinstance(other, Path) else None)

            def __ne__(self, other):
                return not (self == other)

            def __hash__(self):
                return hash(self._path)

            def exists(self):
                return os.path.exists(self._path)

            def absolute(self):
                return Path(os.path.abspath(self._path))

            @property
            def parent(self):
                return Path(os.path.abspath(os.path.join(self._path, os.path.pardir)))

            def resolve(self):
                return Path(os.path.realpath(self._path))

            @property
            def name(self):
                return os.path.basename(self._path)

            @property
            def parts(self):
                return self._path.split(os.sep)

            def is_file(self):
                return os.path.isfile(self._path)

            def is_dir(self):
                return os.path.isdir(self._path)

            def mkdir(self, parents=True, exist_ok=True):
                if not self.exists() and exist_ok:
                    os.makedirs(self._path)

            def read_text(self, encoding="utf-8"):
                with open(self._path, "rb") as file_handler:
                    return file_handler.read().decode(encoding)

            def write_text(self, text, encoding="utf-8"):
                with open(self._path, "wb") as file_handler:
                    file_handler.write(text.encode(encoding))

            def iterdir(self):
                for p in os.listdir(self._path):
                    yield Path(os.path.join(self._path, p))

            @property
            def suffix(self):
                _, ext = os.path.splitext(self.name)
                return ext

            @property
            def stem(self):
                base, _ = os.path.splitext(self.name)
                return base

            @contextmanager
            def open(self, mode="r"):
                with open(self._path, mode) as file_handler:
                    yield file_handler

            @property
            def parents(self):
                result = []
                parts = self.parts
                for i in range(len(parts)):
                    result.append(Path(os.sep.join(parts[0 : i + 1])))
                return result

            def unlink(self):
                os.remove(self._path)

            def with_name(self, name):
                return self.parent / name

            def is_symlink(self):
                return os.path.islink(self._path)

    else:
        from pathlib2 import Path
__all__ = ("Path",)
