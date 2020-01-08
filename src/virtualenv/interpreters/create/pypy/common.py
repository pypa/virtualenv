from __future__ import absolute_import, unicode_literals

import abc

import six

from virtualenv.interpreters.create.via_global_ref.via_global_self_do import ViaGlobalRefSelfDo
from virtualenv.util.path import Path


@six.add_metaclass(abc.ABCMeta)
class PyPy(ViaGlobalRefSelfDo):
    @classmethod
    def supports(cls, interpreter):
        return interpreter.implementation == "PyPy" and super(PyPy, cls).supports(interpreter)

    @property
    def bin_name(self):
        return "bin"

    @property
    def site_packages(self):
        return [self.dest_dir / "site-packages"]

    def link_exe(self):
        host = Path(self.interpreter.system_executable)
        return {
            host: sorted(
                {
                    host.name,
                    self.exe.name,
                    "python{}".format(self.suffix),
                    "python{}{}".format(self.interpreter.version_info.major, self.suffix),
                }
            )
        }

    def setup_python(self):
        super(PyPy, self).setup_python()
        self._add_shared_libs()

    def _add_shared_libs(self):
        # https://bitbucket.org/pypy/pypy/issue/1922/future-proofing-virtualenv
        python_dir = Path(self.interpreter.system_executable).parent
        for libname in self._shared_libs:
            src = python_dir / libname
            if src.exists():
                for to in self._shared_lib_to():
                    self.copier(src, to / libname)

    def _shared_lib_to(self):
        return [self.bin_dir]

    @property
    def _shared_libs(self):
        raise NotImplementedError
