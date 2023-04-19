from __future__ import annotations

from abc import ABCMeta, abstractmethod
from itertools import chain
from operator import attrgetter as attr
from pathlib import Path


def is_name(path):
    return str(path) == path.name


class FakeDataABC(metaclass=ABCMeta):
    """Provides data to mock the `Path`"""

    @property
    @abstractmethod
    def filelist(self):
        """To mock a dir, just mock any child file."""
        raise NotImplementedError("Collection of (str) file paths to mock")

    @property
    def fake_files(self):
        return map(type(self), self.filelist)

    @property
    def fake_dirs(self):
        return set(chain(*map(attr("parents"), self.fake_files)))

    @property
    def contained_fake_names(self):
        return filter(is_name, self.fake_content)

    @property
    def fake_content(self):
        return filter(None, map(self.fake_child, self.fake_files))

    def fake_child(self, path):
        try:
            return path.relative_to(self)
        except ValueError:
            return None


class PathMockABC(FakeDataABC, Path):
    """Mocks the behavior of `Path`"""

    _flavour = getattr(Path(), "_flavour", None)

    if hasattr(_flavour, "altsep"):
        # Allows to pass some tests for Windows via PosixPath.
        _flavour.altsep = _flavour.altsep or "\\"

    def exists(self):
        return self.is_file() or self.is_dir()

    def is_file(self):
        return self in self.fake_files

    def is_dir(self):
        return self in self.fake_dirs

    def resolve(self):
        return self

    def iterdir(self):
        if not self.is_dir():
            raise FileNotFoundError(f"No such mocked dir: '{self}'")
        yield from map(self.joinpath, self.contained_fake_names)


def MetaPathMock(filelist):  # noqa: N802
    """
    Metaclass that creates a `PathMock` class with the `filelist` defined.
    """
    return type("PathMock", (PathMockABC,), {"filelist": filelist})


def mock_files(mocker, pathlist, filelist):
    PathMock = MetaPathMock(set(filelist))  # noqa: N806
    for path in pathlist:
        mocker.patch(path, PathMock)


def mock_pypy_libs(mocker, pypy_creator_cls, libs):
    paths = tuple(set(map(Path, libs)))
    mocker.patch.object(pypy_creator_cls, "_shared_libs", return_value=paths)


def join(*chunks):
    line = "".join(chunks)
    sep = ("\\" in line and "\\") or ("/" in line and "/") or "/"
    return sep.join(chunks)
