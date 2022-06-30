"""
Utilities for accessing files within the virtualenv package without using __file__ so there is no assumption of a
file system.
"""
from __future__ import absolute_import, unicode_literals

import os
import shutil
import sys
from contextlib import contextmanager
from importlib.util import find_spec
from tempfile import mkdtemp

import six

from virtualenv.util.path import Path

if sys.version_info >= (3, 7):
    import importlib.resources as importlib_resources
else:
    import importlib_resources


class PackagePath(object):
    def __init__(self, package):
        self.__package = str(package)

    def __str__(self):
        return self.__package

    def __truediv__(self, name):
        return ResourcePath(self.__package, name)


class ResourcePath(object):
    def __init__(self, package, name):
        self.__package = str(package)
        self.__name = str(name)
        self.__stem, self.__suffix = os.path.splitext(self.__name)

        # Set during .as_path()
        self.__parent = ""
        self.__path = ""

    def read_bytes(self):
        # TODO: Remove branch when this is fixed https://github.com/indygreg/PyOxidizer/issues/237
        if self.suffix == ".py":
            return six.ensure_binary(self.read_text(), encoding="utf-8")

        return importlib_resources.read_binary(self.__package, self.__name)

    def read_text(self, **kwargs):
        # TODO: Remove branch when this is fixed https://github.com/indygreg/PyOxidizer/issues/237
        if self.suffix == ".py":
            spec_string = "{}.{}".format(self.__package, self.__stem)
            spec = find_spec(spec_string)
            return spec.loader.get_source(spec_string)

        return importlib_resources.read_text(self.__package, self.__name, **kwargs)

    @contextmanager
    def as_path(self):
        self.__parent = d = mkdtemp()
        self.__path = os.path.join(self.__parent, self.name)
        try:
            with open(self.__path, "wb") as f:
                f.write(self.read_bytes())

            yield Path(self.__path)
        finally:
            self.__parent = ""
            self.__path = ""
            shutil.rmtree(d)

    @property
    def name(self):
        return self.__name

    @property
    def stem(self):
        return self.__stem

    @property
    def suffix(self):
        return self.__suffix

    @property
    def parent(self):
        return self.__parent or PackagePath(self.__package.rsplit(".", 1)[0])

    def __str__(self):
        return self.__path or self.name
