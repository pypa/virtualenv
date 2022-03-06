import fnmatch

from virtualenv.create.via_global_ref.builtin.pypy.pypy3 import PyPy3Posix
from virtualenv.create.via_global_ref.builtin.ref import ExePathRefToDest, PathRefToDest
from virtualenv.discovery.py_info import PythonInfo
from virtualenv.util.path import Path

# As downloaded from https://www.pypy.org/download.html
PORTABLE_PYPY38 = {
    "platform": "linux",
    "implementation": "PyPy",
    "pypy_version_info": [7, 3, 8, "final", 0],
    "version_info": {
        "major": 3,
        "minor": 8,
        "micro": 12,
        "releaselevel": "final",
        "serial": 0,
    },
    "architecture": 64,
    "version": "3.8.12 (d00b0afd2a5dd3c13fcda75d738262c864c62fa7, Feb 18 2022, 09:52:33)\n"
    "[PyPy 7.3.8 with GCC 10.2.1 20210130 (Red Hat 10.2.1-11)]",
    "os": "posix",
    "prefix": "/tmp/pypy3.8-v7.3.8-linux64",
    "base_prefix": "/tmp/pypy3.8-v7.3.8-linux64",
    "real_prefix": None,
    "base_exec_prefix": "/tmp/pypy3.8-v7.3.8-linux64",
    "exec_prefix": "/tmp/pypy3.8-v7.3.8-linux64",
    "executable": "/tmp/pypy3.8-v7.3.8-linux64/bin/pypy",
    "original_executable": "/tmp/pypy3.8-v7.3.8-linux64/bin/pypy",
    "system_executable": "/tmp/pypy3.8-v7.3.8-linux64/bin/pypy",
    "has_venv": True,
    "path": [
        "/tmp/pypy3.8-v7.3.8-linux64/lib/pypy3.8",
        "/tmp/pypy3.8-v7.3.8-linux64/lib/pypy3.8/site-packages",
    ],
    "file_system_encoding": "utf-8",
    "stdout_encoding": "UTF-8",
    "sysconfig_scheme": None,
    "sysconfig_paths": {
        "stdlib": "{installed_base}/lib/{implementation_lower}{py_version_short}",
        "platstdlib": "{platbase}/lib/{implementation_lower}{py_version_short}",
        "purelib": "{base}/lib/{implementation_lower}{py_version_short}/site-packages",
        "platlib": "{platbase}/lib/{implementation_lower}{py_version_short}/site-packages",
        "include": "{installed_base}/include/{implementation_lower}{py_version_short}{abiflags}",
        "scripts": "{base}/bin",
        "data": "{base}",
    },
    "distutils_install": {
        "purelib": "lib/pypy3.8/site-packages",
        "platlib": "lib/pypy3.8/site-packages",
        "headers": "include/pypy3.8/UNKNOWN",
        "scripts": "bin",
        "data": "",
    },
    "sysconfig": {
        "makefile_filename": "/tmp/pypy3.8-v7.3.8-linux64/lib/pypy3.8/config-3.8-x86_64-linux-gnu/Makefile",
    },
    "sysconfig_vars": {
        "installed_base": "/tmp/pypy3.8-v7.3.8-linux64",
        "implementation_lower": "pypy",
        "py_version_short": "3.8",
        "platbase": "/tmp/pypy3.8-v7.3.8-linux64",
        "base": "/tmp/pypy3.8-v7.3.8-linux64",
        "abiflags": "",
        "PYTHONFRAMEWORK": "",
    },
    "system_stdlib": "/tmp/pypy3.8-v7.3.8-linux64/lib/pypy3.8",
    "system_stdlib_platform": "/tmp/pypy3.8-v7.3.8-linux64/lib/pypy3.8",
    "max_size": 9223372036854775807,
    "_creators": None,
}

# Debian's pypy3 layout, installed to /usr, before 3.8 allowed a /usr prefix
DEB_PYPY37 = {
    "platform": "linux",
    "implementation": "PyPy",
    "pypy_version_info": [7, 3, 7, "final", 0],
    "version_info": {
        "major": 3,
        "minor": 7,
        "micro": 12,
        "releaselevel": "final",
        "serial": 0,
    },
    "architecture": 64,
    "version": "3.7.12 (7.3.7+dfsg-5, Jan 27 2022, 12:27:44)\n[PyPy 7.3.7 with GCC 11.2.0]",
    "os": "posix",
    "prefix": "/usr/lib/pypy3",
    "base_prefix": "/usr/lib/pypy3",
    "real_prefix": None,
    "base_exec_prefix": "/usr/lib/pypy3",
    "exec_prefix": "/usr/lib/pypy3",
    "executable": "/usr/bin/pypy3",
    "original_executable": "/usr/bin/pypy3",
    "system_executable": "/usr/bin/pypy3",
    "has_venv": True,
    "path": [
        "/usr/lib/pypy3/lib_pypy/__extensions__",
        "/usr/lib/pypy3/lib_pypy",
        "/usr/lib/pypy3/lib-python/3",
        "/usr/lib/pypy3/lib-python/3/lib-tk",
        "/usr/lib/pypy3/lib-python/3/plat-linux2",
        "/usr/local/lib/pypy3.7/dist-packages",
        "/usr/lib/python3/dist-packages",
    ],
    "file_system_encoding": "utf-8",
    "stdout_encoding": "UTF-8",
    "sysconfig_scheme": None,
    "sysconfig_paths": {
        "stdlib": "{base}/lib-python/{py_version_short}",
        "platstdlib": "{base}/lib-python/{py_version_short}",
        "purelib": "{base}/../../local/lib/pypy{py_version_short}/lib-python",
        "platlib": "{base}/../../local/lib/pypy{py_version_short}/lib-python",
        "include": "{base}/include",
        "scripts": "{base}/../../local/bin",
        "data": "{base}/../../local",
    },
    "distutils_install": {
        "purelib": "site-packages",
        "platlib": "site-packages",
        "headers": "include/UNKNOWN",
        "scripts": "bin",
        "data": "",
    },
    "sysconfig": {
        "makefile_filename": "/usr/lib/pypy3/lib-python/3.7/config-3.7-x86_64-linux-gnu/Makefile",
    },
    "sysconfig_vars": {
        "base": "/usr/lib/pypy3",
        "py_version_short": "3.7",
        "PYTHONFRAMEWORK": "",
    },
    "system_stdlib": "/usr/lib/pypy3/lib-python/3.7",
    "system_stdlib_platform": "/usr/lib/pypy3/lib-python/3.7",
    "max_size": 9223372036854775807,
    "_creators": None,
}

# Debian's pypy3 >= 3.8, with a /usr prefix
DEB_PYPY38 = {
    "platform": "linux",
    "implementation": "PyPy",
    "pypy_version_info": [7, 3, 8, "final", 0],
    "version_info": {
        "major": 3,
        "minor": 8,
        "micro": 12,
        "releaselevel": "final",
        "serial": 0,
    },
    "architecture": 64,
    "version": "3.8.12 (7.3.8+dfsg-2, Mar 05 2022, 02:04:42)\n[PyPy 7.3.8 with GCC 11.2.0]",
    "os": "posix",
    "prefix": "/usr",
    "base_prefix": "/usr",
    "real_prefix": None,
    "base_exec_prefix": "/usr",
    "exec_prefix": "/usr",
    "executable": "/usr/bin/pypy3",
    "original_executable": "/usr/bin/pypy3",
    "system_executable": "/usr/bin/pypy3",
    "has_venv": True,
    "path": [
        "/usr/lib/pypy3.8",
        "/usr/local/lib/pypy3.8/dist-packages",
        "/usr/lib/python3/dist-packages",
    ],
    "file_system_encoding": "utf-8",
    "stdout_encoding": "UTF-8",
    "sysconfig_scheme": None,
    "sysconfig_paths": {
        "stdlib": "{installed_base}/lib/{implementation_lower}{py_version_short}",
        "platstdlib": "{platbase}/lib/{implementation_lower}{py_version_short}",
        "purelib": "{base}/local/lib/{implementation_lower}{py_version_short}/dist-packages",
        "platlib": "{platbase}/local/lib/{implementation_lower}{py_version_short}/dist-packages",
        "include": "{installed_base}/local/include/{implementation_lower}{py_version_short}{abiflags}",
        "scripts": "{base}/local/bin",
        "data": "{base}",
    },
    "distutils_install": {
        "purelib": "lib/pypy3.8/site-packages",
        "platlib": "lib/pypy3.8/site-packages",
        "headers": "include/pypy3.8/UNKNOWN",
        "scripts": "bin",
        "data": "",
    },
    "sysconfig": {
        "makefile_filename": "/usr/lib/pypy3.8/config-3.8-x86_64-linux-gnu/Makefile",
    },
    "sysconfig_vars": {
        "installed_base": "/usr",
        "implementation_lower": "pypy",
        "py_version_short": "3.8",
        "platbase": "/usr",
        "base": "/usr",
        "abiflags": "",
        "PYTHONFRAMEWORK": "",
    },
    "system_stdlib": "/usr/lib/pypy3.8",
    "system_stdlib_platform": "/usr/lib/pypy3.8",
    "max_size": 9223372036854775807,
    "_creators": None,
}


def assert_contains_exe(sources, src):
    """Assert that the one and only executeable in sources is src"""
    exes = [source for source in sources if isinstance(source, ExePathRefToDest)]
    assert len(exes) == 1
    exe = exes[0]
    assert exe.src.as_posix() == src


def assert_contains_ref(sources, src):
    """Assert that src appears in sources"""
    assert any(source for source in sources if isinstance(source, PathRefToDest) and source.src.as_posix() == src)


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


def inject_fake_path(mocker, existing_paths):
    """Inject FakePath in all the correct places, and set existing_paths"""
    FakePath.existing_paths = existing_paths
    mocker.patch("virtualenv.create.via_global_ref.builtin.pypy.common.Path", FakePath)
    mocker.patch("virtualenv.create.via_global_ref.builtin.pypy.pypy3.Path", FakePath)


def test_portable_pypy3_virtualenvs_get_their_libs(mocker):
    portable_pypy3 = PythonInfo._from_dict(PORTABLE_PYPY38)

    inject_fake_path(
        mocker,
        [
            "/tmp/pypy3.8-v7.3.8-linux64/bin/pypy",
            "/tmp/pypy3.8-v7.3.8-linux64/lib/libgdbm.so.4",
        ],
    )
    mocker.patch.object(
        PyPy3Posix, "_shared_libs", return_value=[Path("/tmp/pypy3.8-v7.3.8-linux64/bin/libpypy3-c.so")]
    )

    sources = list(PyPy3Posix.sources(interpreter=portable_pypy3))
    assert_contains_exe(sources, "/tmp/pypy3.8-v7.3.8-linux64/bin/pypy")
    assert len(sources) > 2
    assert_contains_ref(sources, "/tmp/pypy3.8-v7.3.8-linux64/bin/libpypy3-c.so")
    assert_contains_ref(sources, "/tmp/pypy3.8-v7.3.8-linux64/lib/libgdbm.so.4")


def test_debian_pypy37_virtualenvs(mocker):
    deb_pypy3 = PythonInfo._from_dict(DEB_PYPY37)

    inject_fake_path(mocker, ["/usr/bin/pypy3"])
    mocker.patch.object(PyPy3Posix, "_shared_libs", return_value=[Path("/usr/lib/pypy3/bin/libpypy3-c.so")])

    sources = list(PyPy3Posix.sources(interpreter=deb_pypy3))
    assert_contains_exe(sources, "/usr/bin/pypy3")
    assert_contains_ref(sources, "/usr/lib/pypy3/bin/libpypy3-c.so")
    assert len(sources) == 2


def test_debian_pypy38_virtualenvs_exclude_usr(mocker):
    deb_pypy3 = PythonInfo._from_dict(DEB_PYPY38)

    inject_fake_path(
        mocker,
        [
            "/usr/bin/pypy3",
            "/usr/lib/foo",
        ],
    )
    # libpypy3-c.so lives on the ld search path
    mocker.patch.object(PyPy3Posix, "_shared_libs", return_value=[])

    sources = list(PyPy3Posix.sources(interpreter=deb_pypy3))
    assert_contains_exe(sources, "/usr/bin/pypy3")
    assert len(sources) == 1
