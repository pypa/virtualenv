from __future__ import absolute_import, unicode_literals

from abc import ABCMeta

from six import add_metaclass

from virtualenv.info import IS_WIN
from virtualenv.interpreters.create.via_global_ref.api import ViaGlobalRefApi


@add_metaclass(ABCMeta)
class VirtualenvBuiltin(ViaGlobalRefApi):
    """A creator that does operations itself without delegation"""

    @property
    def bin_name(self):
        raise NotImplementedError

    @property
    def bin_dir(self):
        return self.dest_dir / self.bin_name

    @property
    def lib_dir(self):
        raise NotImplementedError

    @property
    def site_packages(self):
        return [self.lib_dir / "site-packages"]

    @property
    def exe_name(self):
        raise NotImplementedError

    @property
    def exe_base(self):
        raise NotImplementedError

    @property
    def exe(self):
        return self.bin_dir / "{}{}".format(self.exe_base, self.suffix)

    @property
    def suffix(self):
        return ".exe" if IS_WIN else ""
