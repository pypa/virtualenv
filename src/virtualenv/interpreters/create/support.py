from __future__ import absolute_import, unicode_literals

from abc import ABCMeta

from six import add_metaclass

from .creator import Creator


@add_metaclass(ABCMeta)
class Python2Supports(Creator):
    @classmethod
    def supports(cls, interpreter):
        return interpreter.version_info.major == 2 and super(Python2Supports, cls).supports(interpreter)


@add_metaclass(ABCMeta)
class Python3Supports(Creator):
    @classmethod
    def supports(cls, interpreter):
        return interpreter.version_info.major == 3 and super(Python3Supports, cls).supports(interpreter)


@add_metaclass(ABCMeta)
class PosixSupports(Creator):
    @classmethod
    def supports(cls, interpreter):
        return interpreter.os == "posix" and super(PosixSupports, cls).supports(interpreter)


@add_metaclass(ABCMeta)
class WindowsSupports(Creator):
    @classmethod
    def supports(cls, interpreter):
        return interpreter.os == "nt" and super(WindowsSupports, cls).supports(interpreter)
