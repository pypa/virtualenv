import fnmatch
from abc import ABC, abstractmethod

from virtualenv.util.path import Path


class PathMockBase(ABC, Path):
    """A base class to mock the `virtualenv.util.path.Path`."""

    _flavour = getattr(Path(), "_flavour", None)
    sep = getattr(_flavour, "sep", "/")

    @property
    @abstractmethod
    def mocked_paths(self):
        """Return a list of paths considered to existing."""
        raise NotImplementedError("List of paths you want to mock")

    @property
    def prefix(self):
        return self.as_posix() + self.sep

    def exists(self):
        return self.as_posix() in self.mocked_paths or self.is_dir()

    def glob(self, glob):
        pattern = self.prefix + glob
        matched_paths = fnmatch.filter(self.mocked_paths, pattern)
        yield from map(type(self), matched_paths)

    def is_dir(self):
        return any(map(self.has_prefix, self.mocked_paths))

    def iterdir(self):
        files = filter(self.is_file_path, self.mocked_paths)
        yield from map(type(self), files)

    def resolve(self):
        return self

    def is_file_path(self, path):
        return self.has_prefix(path) and self.sep not in self.tail(path)

    def has_prefix(self, path):
        return path.startswith(self.prefix)

    def tail(self, path):
        return path[len(self.prefix) :]

    def __div__(self, key):
        return type(self)(super(PathMockBase, self).__div__(key))

    def __truediv__(self, key):
        return type(self)(super(PathMockBase, self).__truediv__(key))


def path_mock(paths):
    """
    Metaclass that creates a `PathMock` class with the `mocked_paths` defined,
    based on the `PathMockBase`.
    """
    return type("PathMock", (PathMockBase,), {"mocked_paths": paths})


def files(mocker, path_list, file_list):
    PathMock = path_mock(file_list)
    for path in path_list:
        mocker.patch(path, PathMock)


def pypy_libs(mocker, pypy_creator_class, libs):
    paths = tuple(map(Path, libs))
    mocker.patch.object(pypy_creator_class, "_shared_libs", return_value=paths)
