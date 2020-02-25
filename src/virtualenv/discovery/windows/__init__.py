from __future__ import absolute_import, unicode_literals

from ..py_info import PythonInfo
from ..py_spec import PythonSpec
from .pep514 import discover_pythons


class Pep514PythonInfo(PythonInfo):
    """"""


def propose_interpreters(spec, cache_dir):
    # see if PEP-514 entries are good
    for name, major, minor, arch, exe, _ in discover_pythons():
        # pre-filter
        registry_spec = PythonSpec(None, name, major, minor, None, arch, exe)
        if registry_spec.satisfies(spec):
            interpreter = Pep514PythonInfo.from_exe(exe, cache_dir, raise_on_error=False)
            if interpreter is not None:
                if interpreter.satisfies(spec, impl_must_match=True):
                    yield interpreter
