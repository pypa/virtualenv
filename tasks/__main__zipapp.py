from __future__ import annotations

import json
import os
import sys
import zipfile
from functools import cached_property
from importlib.abc import SourceLoader
from importlib.util import spec_from_file_location

ABS_HERE = os.path.abspath(os.path.dirname(__file__))


class VersionPlatformSelect:
    def __init__(self) -> None:
        zipapp = ABS_HERE
        self.archive = zipapp
        self._zip_file = zipfile.ZipFile(zipapp)
        self.modules = self._load("modules.json")
        self.distributions = self._load("distributions.json")
        self.__cache = {}

    def _load(self, of_file):
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

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._zip_file.close()

    def find_mod(self, fullname):
        if fullname in self.modules:
            return self.modules[fullname]
        return None

    def get_filename(self, fullname):
        zip_path = self.find_mod(fullname)
        return None if zip_path is None else os.path.join(ABS_HERE, zip_path)

    def get_data(self, filename):
        if filename.startswith(ABS_HERE):
            # keep paths relative from the zipfile
            filename = filename[len(ABS_HERE) + 1 :]
            filename = filename.lstrip(os.sep)
        if sys.platform == "win32":
            # paths within the zipfile is always /, fixup on Windows to transform \ to /
            filename = "/".join(filename.split(os.sep))
        with self._zip_file.open(filename) as file_handler:
            return file_handler.read()

    def find_distributions(self, context):
        dist_class = versioned_distribution_class()
        name = context.name
        if name in self.distributions:
            result = dist_class(file_loader=self.get_data, dist_path=self.distributions[name])
            yield result

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(path={ABS_HERE})"

    def _register_distutils_finder(self):  # noqa: C901
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
            def __init__(self, path, loader) -> None:
                self.path = path
                self.loader = loader

            def find(self, name):
                return Resource(self.path, name, self.loader)

            def iterator(self, resource_name):
                resource = self.find(resource_name)
                if resource is not None:
                    todo = [resource]
                    while todo:
                        resource = todo.pop(0)
                        yield resource
                        if resource.is_container:
                            resource_name = resource.name
                            for name in resource.resources:
                                child = self.find(f"{resource_name}/{name}" if resource_name else name)
                                if child.is_container:
                                    todo.append(child)
                                else:
                                    yield child

        from distlib.resources import register_finder  # noqa: PLC0415

        zip_file = self._zip_file
        register_finder(self, lambda module: DistlibFinder(os.path.dirname(module.__file__), self))


_VER_DISTRIBUTION_CLASS = None


def versioned_distribution_class():
    global _VER_DISTRIBUTION_CLASS  # noqa: PLW0603
    if _VER_DISTRIBUTION_CLASS is None:
        from importlib.metadata import Distribution  # noqa: PLC0415

        class VersionedDistribution(Distribution):
            def __init__(self, file_loader, dist_path) -> None:
                self.file_loader = file_loader
                self.dist_path = dist_path

            def read_text(self, filename):
                return self.file_loader(self.locate_file(filename)).decode("utf-8")

            def locate_file(self, path):
                return os.path.join(self.dist_path, path)

        _VER_DISTRIBUTION_CLASS = VersionedDistribution
    return _VER_DISTRIBUTION_CLASS


class VersionedFindLoad(VersionPlatformSelect, SourceLoader):
    def find_spec(self, fullname, path, target=None):  # noqa: ARG002
        zip_path = self.find_mod(fullname)
        if zip_path is not None:
            return spec_from_file_location(name=fullname, loader=self)
        return None

    def module_repr(self, module):
        raise NotImplementedError


def run():
    with VersionedFindLoad() as finder:
        sys.meta_path.insert(0, finder)
        finder._register_distutils_finder()  # noqa: SLF001
        from virtualenv.__main__ import run as run_virtualenv  # noqa: PLC0415, PLC2701

        run_virtualenv()


if __name__ == "__main__":
    run()
