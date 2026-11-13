from __future__ import annotations

import json
import os
import sys
import zipfile
from functools import cached_property
from importlib.abc import SourceLoader
from importlib.util import spec_from_file_location
from typing import TYPE_CHECKING, Any, Final

if TYPE_CHECKING:
    from collections.abc import Iterator
    from importlib.machinery import ModuleSpec
    from importlib.metadata import Distribution, DistributionFinder
    from types import ModuleType, TracebackType
    from typing import Self

ABS_HERE: Final[str] = os.path.abspath(os.path.dirname(__file__))


def _run() -> None:
    with VersionedFindLoad():
        # must import inside VersionedFindLoad, so the zipapp finders are active
        from virtualenv.__main__ import run as run_virtualenv  # ruff:ignore[import-outside-top-level]

        run_virtualenv()


class _VersionPlatformSelect:
    def __init__(self) -> None:
        zipapp = ABS_HERE
        self.archive = zipapp
        self._zip_file = zipfile.ZipFile(zipapp)
        self.modules = self._load("modules.json")
        self.distributions = self._load("distributions.json")
        self.__cache = {}

    def _load(self, of_file: str) -> dict[str, str]:
        version = ".".join(str(i) for i in sys.version_info[0:2])
        per_version = json.loads(self.get_data(of_file).decode())
        all_platforms = per_version[version] if version in per_version else per_version["3.9"]
        content = all_platforms.get("==any", {})  # start will all platforms
        not_us = f"!={sys.platform}"
        for key, value in all_platforms.items():  # now override that with not platform
            if key.startswith("!=") and key != not_us:
                content.update(value)
        content.update(all_platforms.get(f"=={sys.platform}", {}))  # and finish it off with our platform
        return content

    def get_data(self, filename: str) -> bytes:
        if filename.startswith(ABS_HERE):
            # keep paths relative from the zipfile
            filename = filename[len(ABS_HERE) + 1 :]
            filename = filename.lstrip(os.sep)
        if sys.platform == "win32":
            # paths within the zipfile is always /, fixup on Windows to transform \ to /
            filename = "/".join(filename.split(os.sep))
        with self._zip_file.open(filename) as file_handler:
            return file_handler.read()

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self, exc_type: type[BaseException] | None, exc_val: BaseException | None, exc_tb: TracebackType | None
    ) -> None:
        self._zip_file.close()

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(path={ABS_HERE})"

    def get_filename(self, fullname: str) -> str | None:
        zip_path = self.find_mod(fullname)
        return None if zip_path is None else os.path.join(ABS_HERE, zip_path)

    def find_mod(self, fullname: str) -> str | None:
        if fullname in self.modules:
            return self.modules[fullname]
        return None

    def find_distributions(self, context: DistributionFinder.Context) -> Iterator[Distribution]:
        dist_class = _versioned_distribution_class()
        if context.name is None:
            return
        if (name := context.name.replace("_", "-")) in self.distributions:
            yield dist_class(file_loader=self.get_data, dist_path=self.distributions[name])

    # the distlib finder classes are defined here, they close over self
    def _register_distutils_finder(self) -> None:  # ruff:ignore[complex-structure]
        if "distlib" not in self.modules:
            return

        class Resource:
            def __init__(self, path: str, name: str, loader: SourceLoader) -> None:
                self.path = os.path.join(path, name)
                self._name = name
                self.loader = loader

            @cached_property
            def name(self) -> str:
                return os.path.basename(self._name)

            @property
            def bytes(self) -> bytes:
                return self.loader.get_data(self._name)

            @property
            def is_container(self) -> bool:
                return len(self.resources) > 1

            @cached_property
            def resources(self) -> list[str]:
                return [
                    i.filename
                    for i in (
                        (j for j in zip_file.filelist if j.filename.startswith(f"{self._name}/"))
                        if self._name
                        else zip_file.filelist
                    )
                ]

        class DistlibFinder:
            # distlib passes an untyped loader to its finder
            def __init__(self, path: str, loader: Any) -> None:  # ruff:ignore[any-type]
                self.path = path
                self.loader = loader

            def iterator(self, resource_name: str) -> Iterator[Resource]:
                if (resource := self.find(resource_name)) is not None:
                    todo = [resource]
                    while todo:
                        resource = todo.pop(0)
                        yield resource
                        if resource.is_container:
                            for child in self._children(resource):
                                if child.is_container:
                                    todo.append(child)
                                else:
                                    yield child

            # distlib's resource finder returns resources of any type
            def find(self, name: str) -> Any:  # ruff:ignore[any-type]
                return Resource(self.path, name, self.loader)

            def _children(self, resource: Resource) -> Iterator[Resource]:
                for name in resource.resources:
                    yield self.find(f"{resource.name}/{name}" if resource.name else name)

        # distlib is importable only once the zipapp is loaded, so the import is deferred
        from distlib.resources import register_finder  # ruff:ignore[import-outside-top-level]

        zip_file = self._zip_file
        register_finder(self, lambda module: DistlibFinder(os.path.dirname(module.__file__), self))


_VER_DISTRIBUTION_CLASS = None


def _versioned_distribution_class() -> type:
    # a cache of the versioned class, filled on first use
    global _VER_DISTRIBUTION_CLASS  # ruff:ignore[global-statement]
    if _VER_DISTRIBUTION_CLASS is None:
        # importlib.metadata is imported only when the versioned class is built
        from importlib.metadata import Distribution  # ruff:ignore[import-outside-top-level]

        class VersionedDistribution(Distribution):
            # importlib.metadata passes its file loader untyped
            def __init__(self, file_loader: Any, dist_path: str) -> None:  # ruff:ignore[any-type]
                self.file_loader = file_loader
                self.dist_path = dist_path

            def read_text(self, filename: str) -> str:
                return self.file_loader(self.locate_file(filename)).decode("utf-8")

            def locate_file(self, path: str) -> str:
                return os.path.join(self.dist_path, path)

        _VER_DISTRIBUTION_CLASS = VersionedDistribution
    return _VER_DISTRIBUTION_CLASS


class VersionedFindLoad(_VersionPlatformSelect, SourceLoader):  # simplint: ignore[unexported-public-name]  # zipapp bootstrap  # fmt: skip
    def __enter__(self) -> Self:
        sys.path.insert(0, self.archive)
        sys.meta_path.insert(0, self)
        self._register_distutils_finder()
        return self

    def __exit__(
        self, exc_type: type[BaseException] | None, exc_val: BaseException | None, exc_tb: TracebackType | None
    ) -> None:
        sys.meta_path.remove(self)
        sys.path.remove(self.archive)
        super().__exit__(exc_type, exc_val, exc_tb)

    # the meta path protocol passes these, the finder ignores target and path
    def find_spec(self, fullname: str, path: Any, target: ModuleType | None = None) -> ModuleSpec | None:  # ruff:ignore[unused-method-argument, any-type]
        if self.find_mod(fullname) is not None:
            return spec_from_file_location(name=fullname, loader=self)
        return None

    def module_repr(self, module: ModuleType) -> str:
        raise NotImplementedError


if __name__ == "__main__":
    _run()


__all__ = []
