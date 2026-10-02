from __future__ import annotations

import logging
from email.parser import HeaderParser
from operator import attrgetter
from typing import TYPE_CHECKING, Final
from zipfile import ZipFile

from packaging.specifiers import InvalidSpecifier, SpecifierSet
from packaging.version import Version as PackagingVersion

if TYPE_CHECKING:
    from pathlib import Path

_LOGGER: Final[logging.Logger] = logging.getLogger(__name__)
# https://packaging.python.org/en/latest/specifications/binary-distribution-format/#file-name-convention
# {distribution}-{version}(-{build tag})?-{python tag}-{abi tag}-{platform tag}.whl
_MIN_WHEEL_NAME_PARTS: Final[int] = 5


def discover_wheels(from_folder: Path, distribution: str, version: str | None, for_py_version: str) -> list[Wheel]:
    return sorted(
        (
            wheel
            for filename in from_folder.iterdir()
            if (wheel := Wheel.from_path(filename))
            and wheel.distribution == distribution
            and (version is None or wheel.version == version)
            and wheel.support_py(for_py_version)
        ),
        key=attrgetter("parsed_version", "distribution"),
        reverse=True,
    )


class Wheel:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._parts = path.stem.split("-")

    @classmethod
    def from_path(cls, path: Path) -> Wheel | None:
        if path.suffix == ".whl" and len(path.stem.split("-")) >= _MIN_WHEEL_NAME_PARTS:
            return cls(path)
        return None

    def support_py(self, py_version: str) -> bool:
        """Check whether ``Requires-Python`` admits ``py_version``, a ``major.minor`` string."""
        name = f"{self.distribution}-{self.version}.dist-info/METADATA"
        with ZipFile(str(self.path), "r") as zip_file:
            requires = HeaderParser().parsestr(zip_file.read(name).decode("utf-8")).get("Requires-Python")
        if requires is None:
            return True
        try:
            return SpecifierSet(requires).contains(py_version)
        except InvalidSpecifier:
            # skip the wheel as pip does, rather than abort seeding or override the verified embedded wheel
            _LOGGER.warning("skip %s, its Requires-Python %r is not a valid specifier", self.path, requires)
            return False

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
        return PackagingVersion(version).release

    @property
    def parsed_version(self) -> PackagingVersion:
        return PackagingVersion(self.version)

    @property
    def name(self) -> str:
        return self.path.name

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self.path})"

    def __str__(self) -> str:
        return str(self.path)


class Version:
    #: the version bundled with virtualenv
    bundle: Final[str] = "bundle"
    embed: Final[str] = "embed"
    #: custom version handlers
    non_version: Final[tuple[str, str]] = (bundle, embed)

    @staticmethod
    def as_pip_req(distribution: str, version: str | None) -> str:
        return f"{distribution}{Version.as_version_spec(version)}"

    @staticmethod
    def as_version_spec(version: str | None) -> str:
        return "" if (of_version := Version.of_version(version)) is None else f"=={of_version}"

    @staticmethod
    def of_version(value: str | None) -> str | None:
        return None if value in Version.non_version else value


__all__ = [
    "Version",
    "Wheel",
    "discover_wheels",
]
