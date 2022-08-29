import abc
from pathlib import Path

from virtualenv.create.describe import PosixSupports, Python3Supports
from virtualenv.create.via_global_ref.builtin.ref import ExePathRefToDest, RefMust, RefWhen
from virtualenv.create.via_global_ref.builtin.via_global_self_do import ViaGlobalRefVirtualenvBuiltin


class GraalPy(ViaGlobalRefVirtualenvBuiltin, Python3Supports, metaclass=abc.ABCMeta):
    @property
    def stdlib(self):
        # Pretending that the stdlib is the site-packages location prevents ViaGlobalRefVirtualenvBuiltin from creating
        # an empty dummy directory for the stdlib (the site-packages dir will already exist and is actually useful).
        # GraalPy virtual environments always use the host python standard library.
        return self.dest / "lib" / f"python{self.interpreter.version_release_str}" / "site-packages"

    @classmethod
    def can_describe(cls, interpreter):
        return interpreter.implementation == "GraalVM" and super().can_describe(interpreter)

    @classmethod
    def exe_stem(cls):
        return "graalpy"

    @classmethod
    def exe_names(cls, interpreter):
        return {
            cls.exe_stem(),
            "python",
            f"python{interpreter.version_info.major}",
        }

    @classmethod
    def _executables(cls, interpreter):
        host = Path(interpreter.system_executable)
        targets = sorted(f"{name}{GraalPy.suffix}" for name in cls.exe_names(interpreter))
        # GraalPy supports only symlinks, because the launcher is linked with a shared library using a relative path
        # We may copy the shared library also if we want to support the copy option too
        yield host, targets, RefMust.SYMLINK, RefWhen.ANY

    @classmethod
    def sources(cls, interpreter):
        extra_tools = getattr(interpreter, "extra_tools", None)
        if extra_tools:
            for (src, targets) in extra_tools.items():
                yield ExePathRefToDest(
                    Path(src), dest=cls.to_bin, targets=targets, must=RefMust.SYMLINK, when=RefWhen.ANY
                )
        yield from super().sources(interpreter)


class GraalPyPosix(GraalPy, PosixSupports):
    """GraalPy 3 on POSIX"""

    pass
