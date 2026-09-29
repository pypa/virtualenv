from __future__ import annotations

import re
from operator import attrgetter
from typing import TYPE_CHECKING
from zipfile import ZipFile

if TYPE_CHECKING:
    from pathlib import Path

# The leading dotted numbers of a PEP 440 version, which fix where it sits relative to other releases.
_RELEASE_RE = re.compile(r"^\d+(?:\.\d+)*")
_STAGE_NUMBER_RE = re.compile(r"^\d*")

# What follows those numbers decides the order within a release: a pre-release sorts before the final
# release, and a post or dev release after it. The suffix used to be dropped, so 26.2.1rc1 compared
# equal to 26.2 and a pinned pre-release resolved to the wrong wheel.
_STAGE_RANK: dict[str, int] = {"a": 0, "b": 1, "rc": 2, "": 3, "post": 4, "dev": 5}
_STAGES: tuple[str, ...] = ("dev", "post", "a", "b", "rc")
#: an absent stage sorts below a real one, so a release with no post-release outranks 2.0.post1
_NO_STAGE: int = -1
#: a dev release sorts below the release it belongs to, so an absent dev has to sort above a real one
_NO_DEV: int = 99
#: how many release numbers the key holds, so 2.0 and 2.0.1 order on the numbers rather than on the stage
_RELEASE_PADDING: int = 3


def _stage_number(after_stage: str) -> int:
    """Read the number that follows a stage marker, defaulting to 0 when it carries none."""
    found = _STAGE_NUMBER_RE.match(after_stage)
    return int(found.group() or 0) if found is not None else 0


class Wheel:
    def __init__(self, path: Path) -> None:
        # https://www.python.org/dev/peps/pep-0427/#file-name-convention
        # The wheel filename is {distribution}-{version}(-{build tag})?-{python tag}-{abi tag}-{platform tag}.whl
        self.path = path
        self._parts = path.stem.split("-")

    @classmethod
    def from_path(cls, path: Path) -> Wheel | None:
        if path is not None and path.suffix == ".whl" and len(path.stem.split("-")) >= 5:  # ruff:ignore[magic-value-comparison]
            return cls(path)
        return None

    @property
    def distribution(self) -> str:
        return self._parts[0]

    @property
    def version(self) -> str:
        return self._parts[1]

    @property
    def version_tuple(self) -> tuple[int, ...]:
        return self.as_version_tuple(self.version)

    @staticmethod
    def as_version_tuple(version: str) -> tuple[int, ...]:
        """Build a sortable key for a PEP 440 version.

        The key lays out the release numbers first, then the dev, pre-release and post-release stages, so ``2.0`` and
        ``2.0.1`` order on the numbers first and ``2.0.1rc1`` orders below ``2.0.1``. Comparing these keys gives the PEP
        440 ordering without depending on ``packaging`` at runtime.

        :param version: the version part of a wheel filename, for example ``26.2.1rc1``.

        :returns: a key that sorts the same way :mod:`packaging` would sort those versions.

        :raises ValueError: if no leading version number is present at all.

        """
        match = _RELEASE_RE.match(version)
        if match is None:
            raise ValueError(version)
        numbers = tuple(int(i) for i in match.group().split("."))
        # a post or dev release is written with a dot, as in 2.0.post1, while a pre-release has none
        rest = version[match.end() :].lstrip(".")
        # each stage is a rank and its number; dev has the opposite sense, absent meaning "not a dev release"
        pre, post, dev = (_STAGE_RANK[""], 0), (_NO_STAGE, 0), (_NO_DEV, 0)
        for stage in _STAGES:
            if not rest.startswith(stage):
                continue
            found = _STAGE_RANK[stage], _stage_number(rest[len(stage) :])
            if stage in {"a", "b", "rc"}:
                pre = found
            elif stage == "post":
                post = found
            else:
                dev = found
            break
        # pad the release numbers so 2.0 and 2.0.1 compare on the numbers, not on the stage that follows
        padded = (*numbers, *([0] * (_RELEASE_PADDING - len(numbers))))
        return (*padded[:_RELEASE_PADDING], *dev, *pre, *post)

    @property
    def name(self) -> str:
        return self.path.name

    def support_py(self, py_version: str) -> bool:
        name = f"{'-'.join(self.path.stem.split('-')[0:2])}.dist-info/METADATA"
        with ZipFile(str(self.path), "r") as zip_file:
            metadata = zip_file.read(name).decode("utf-8")
        marker = "Requires-Python:"
        requires = next((i[len(marker) :] for i in metadata.splitlines() if i.startswith(marker)), None)
        if requires is None:  # if it does not specify a python requires the assumption is compatible
            return True
        py_version_int = tuple(int(i) for i in py_version.split("."))
        for require in (i.strip() for i in requires.split(",")):
            # https://www.python.org/dev/peps/pep-0345/#version-specifiers
            for operator, check in [
                ("!=", lambda v: py_version_int != v),
                ("==", lambda v: py_version_int == v),
                ("<=", lambda v: py_version_int <= v),
                (">=", lambda v: py_version_int >= v),
                ("<", lambda v: py_version_int < v),
                (">", lambda v: py_version_int > v),
            ]:
                if require.startswith(operator):
                    ver_str = require[len(operator) :].strip()
                    version = tuple((int(i) if i != "*" else None) for i in ver_str.split("."))[0:2]
                    if not check(version):
                        return False
                    break
        return True

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self.path})"

    def __str__(self) -> str:
        return str(self.path)


def discover_wheels(from_folder: Path, distribution: str, version: str | None, for_py_version: str) -> list[Wheel]:
    wheels = []
    for filename in from_folder.iterdir():
        wheel = Wheel.from_path(filename)
        if (
            wheel
            and wheel.distribution == distribution
            and (version is None or wheel.version == version)
            and wheel.support_py(for_py_version)
        ):
            wheels.append(wheel)
    return sorted(wheels, key=attrgetter("version_tuple", "distribution"), reverse=True)


class Version:
    #: the version bundled with virtualenv
    bundle = "bundle"
    embed = "embed"
    #: custom version handlers
    non_version = (bundle, embed)

    @staticmethod
    def of_version(value: str | None) -> str | None:
        return None if value in Version.non_version else value

    @staticmethod
    def as_pip_req(distribution: str, version: str | None) -> str:
        return f"{distribution}{Version.as_version_spec(version)}"

    @staticmethod
    def as_version_spec(version: str | None) -> str:
        of_version = Version.of_version(version)
        return "" if of_version is None else f"=={of_version}"


__all__ = [
    "Version",
    "Wheel",
    "discover_wheels",
]
