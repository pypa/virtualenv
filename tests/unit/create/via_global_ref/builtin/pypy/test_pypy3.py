from __future__ import absolute_import, unicode_literals

import fnmatch

from virtualenv.create.via_global_ref.builtin.pypy.pypy3 import PyPy3Posix
from virtualenv.create.via_global_ref.builtin.ref import ExePathRefToDest, PathRefToDest
from virtualenv.discovery.py_info import PythonInfo
from virtualenv.util.path import Path


class FakePath(Path):
    """
    A Path() fake that only knows about files in existing_paths and the
    directories that contain them.
    """

    existing_paths = []

    if hasattr(Path(""), "_flavour"):
        _flavour = Path("")._flavour

    def exists(self):
        return self.as_posix() in self.existing_paths or self.is_dir()

    def glob(self, glob):
        pattern = self.as_posix() + "/" + glob
        for path in fnmatch.filter(self.existing_paths, pattern):
            yield FakePath(path)

    def is_dir(self):
        prefix = self.as_posix() + "/"
        return any(True for path in self.existing_paths if path.startswith(prefix))

    def iterdir(self):
        prefix = self.as_posix() + "/"
        for path in self.existing_paths:
            if path.startswith(prefix) and "/" not in path[len(prefix) :]:
                yield FakePath(path)

    def resolve(self):
        return self

    def __div__(self, key):
        return FakePath(super(FakePath, self).__div__(key))

    def __truediv__(self, key):
        return FakePath(super(FakePath, self).__truediv__(key))


def assert_contains_exe(sources, src):
    """Assert that the one and only executeable in sources is src"""
    exes = [source for source in sources if isinstance(source, ExePathRefToDest)]
    assert len(exes) == 1
    exe = exes[0]
    assert exe.src.as_posix() == src


def assert_contains_ref(sources, src):
    """Assert that src appears in sources"""
    assert any(source for source in sources if isinstance(source, PathRefToDest) and source.src.as_posix() == src)


def inject_fake_path(mocker, existing_paths):
    """Inject FakePath in all the correct places, and set existing_paths"""
    FakePath.existing_paths = existing_paths
    mocker.patch("virtualenv.create.via_global_ref.builtin.pypy.common.Path", FakePath)
    mocker.patch("virtualenv.create.via_global_ref.builtin.pypy.pypy3.Path", FakePath)


def _load_pypi_info(name):
    return PythonInfo._from_json((Path(__file__).parent / "{}.json".format(name)).read_text())


def test_portable_pypy3_virtualenvs_get_their_libs(mocker):
    paths = ["/tmp/pypy3.8-v7.3.8-linux64/bin/pypy", "/tmp/pypy3.8-v7.3.8-linux64/lib/libgdbm.so.4"]
    inject_fake_path(mocker, paths)
    path = Path("/tmp/pypy3.8-v7.3.8-linux64/bin/libpypy3-c.so")
    mocker.patch.object(PyPy3Posix, "_shared_libs", return_value=[path])

    sources = list(PyPy3Posix.sources(interpreter=_load_pypi_info("portable_pypy38")))
    assert_contains_exe(sources, "/tmp/pypy3.8-v7.3.8-linux64/bin/pypy")
    assert len(sources) > 2
    assert_contains_ref(sources, "/tmp/pypy3.8-v7.3.8-linux64/bin/libpypy3-c.so")
    assert_contains_ref(sources, "/tmp/pypy3.8-v7.3.8-linux64/lib/libgdbm.so.4")


def test_debian_pypy37_virtualenvs(mocker):
    # Debian's pypy3 layout, installed to /usr, before 3.8 allowed a /usr prefix
    inject_fake_path(mocker, ["/usr/bin/pypy3"])
    mocker.patch.object(PyPy3Posix, "_shared_libs", return_value=[Path("/usr/lib/pypy3/bin/libpypy3-c.so")])
    sources = list(PyPy3Posix.sources(interpreter=_load_pypi_info("deb_pypy37")))
    assert_contains_exe(sources, "/usr/bin/pypy3")
    assert_contains_ref(sources, "/usr/lib/pypy3/bin/libpypy3-c.so")
    assert len(sources) == 2


def test_debian_pypy38_virtualenvs_exclude_usr(mocker):
    inject_fake_path(mocker, ["/usr/bin/pypy3", "/usr/lib/foo"])
    # libpypy3-c.so lives on the ld search path
    mocker.patch.object(PyPy3Posix, "_shared_libs", return_value=[])

    sources = list(PyPy3Posix.sources(interpreter=_load_pypi_info("deb_pypy38")))
    assert_contains_exe(sources, "/usr/bin/pypy3")
    assert len(sources) == 1
