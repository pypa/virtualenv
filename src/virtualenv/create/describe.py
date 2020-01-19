from __future__ import absolute_import, print_function, unicode_literals

from abc import ABCMeta
from collections import OrderedDict

from six import add_metaclass, ensure_text

from virtualenv.info import IS_WIN
from virtualenv.util.path import Path


@add_metaclass(ABCMeta)
class Describe(object):
    """Given a host interpreter tell us information about what the created interpreter might look like"""

    suffix = ".exe" if IS_WIN else ""

    def __init__(self, dest, interpreter):
        self.interpreter = interpreter
        self.dest = dest
        self._stdlib = None
        self._system_stdlib = None
        self._conf_vars = None

    @property
    def bin_dir(self):
        return self.script_dir

    @property
    def script_dir(self):
        return self.dest / Path(self.interpreter.distutils_install["scripts"])

    @property
    def purelib(self):
        return self.dest / self.interpreter.distutils_install["purelib"]

    @property
    def platlib(self):
        return self.dest / self.interpreter.distutils_install["platlib"]

    @property
    def libs(self):
        return list(OrderedDict(((self.platlib, None), (self.purelib, None))).keys())

    @property
    def stdlib(self):
        if self._stdlib is None:
            self._stdlib = Path(self.interpreter.sysconfig_path("stdlib", config_var=self._config_vars))
        return self._stdlib

    @property
    def _config_vars(self):
        if self._conf_vars is None:
            self._conf_vars = self._calc_config_vars(ensure_text(str(self.dest)))
        return self._conf_vars

    def _calc_config_vars(self, to):
        return {
            k: (to if v.startswith(self.interpreter.prefix) else v) for k, v in self.interpreter.sysconfig_vars.items()
        }

    @classmethod
    def can_describe(cls, interpreter):
        """Knows means it knows how the output will look"""
        return True

    @property
    def env_name(self):
        return ensure_text(self.dest.parts[-1])

    @property
    def exe(self):
        return self.bin_dir / "{}{}".format(self.exe_stem(), self.suffix)

    @classmethod
    def exe_stem(cls):
        """executable name without suffix - there seems to be no standard way to get this without creating it"""
        raise NotImplementedError


@add_metaclass(ABCMeta)
class Python2Supports(Describe):
    @classmethod
    def can_describe(cls, interpreter):
        return interpreter.version_info.major == 2 and super(Python2Supports, cls).can_describe(interpreter)


@add_metaclass(ABCMeta)
class Python3Supports(Describe):
    @classmethod
    def can_describe(cls, interpreter):
        return interpreter.version_info.major == 3 and super(Python3Supports, cls).can_describe(interpreter)


@add_metaclass(ABCMeta)
class PosixSupports(Describe):
    @classmethod
    def can_describe(cls, interpreter):
        return interpreter.os == "posix" and super(PosixSupports, cls).can_describe(interpreter)


@add_metaclass(ABCMeta)
class WindowsSupports(Describe):
    @classmethod
    def can_describe(cls, interpreter):
        return interpreter.os == "nt" and super(WindowsSupports, cls).can_describe(interpreter)
