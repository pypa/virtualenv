from __future__ import absolute_import, unicode_literals

import abc
import json
import os

from six import add_metaclass

from virtualenv.create.describe import Python2Supports
from virtualenv.create.via_global_ref.builtin.ref import PathRefToDest
from virtualenv.info import IS_ZIPAPP
from virtualenv.util.path import Path
from virtualenv.util.six import ensure_text
from virtualenv.util.zipapp import read as read_from_zipapp

from ..via_global_self_do import ViaGlobalRefVirtualenvBuiltin

HERE = Path(os.path.abspath(__file__)).parent


@add_metaclass(abc.ABCMeta)
class Python2(ViaGlobalRefVirtualenvBuiltin, Python2Supports):
    def create(self):
        """Perform operations needed to make the created environment work on Python 2"""
        super(Python2, self).create()
        # install a patched site-package, the default Python 2 site.py is not smart enough to understand pyvenv.cfg,
        # so we inject a small shim that can do this
        site_py = self.stdlib / "site.py"
        custom_site = get_custom_site()
        if IS_ZIPAPP:
            custom_site_text = read_from_zipapp(custom_site)
        else:
            custom_site_text = custom_site.read_text()
        expected = json.dumps([os.path.relpath(ensure_text(str(i)), ensure_text(str(site_py))) for i in self.libs])

        custom_site_text = custom_site_text.replace("___EXPECTED_SITE_PACKAGES___", expected)

        reload_code = os.linesep.join("    {}".format(i) for i in self.reload_code.splitlines()).lstrip()
        custom_site_text = custom_site_text.replace("# ___RELOAD_CODE___", reload_code)

        skip_rewrite = os.linesep.join("            {}".format(i) for i in self.skip_rewrite.splitlines()).lstrip()
        custom_site_text = custom_site_text.replace("# ___SKIP_REWRITE____", skip_rewrite)

        site_py.write_text(custom_site_text)

    @property
    def reload_code(self):
        return 'reload(sys.modules["site"])  # noqa # call system site.py to setup import libraries'

    @property
    def skip_rewrite(self):
        return ""

    @classmethod
    def sources(cls, interpreter):
        for src in super(Python2, cls).sources(interpreter):
            yield src
        # install files needed to run site.py
        for req in cls.modules():

            # the compiled path is optional, but refer to it if exists
            module_compiled_path = interpreter.stdlib_path("{}.pyc".format(req))
            has_compile = module_compiled_path.exists()
            if has_compile:
                yield PathRefToDest(module_compiled_path, dest=cls.to_stdlib)

            # stdlib module src may be missing if the interpreter allows it by falling back to the compiled
            module_path = interpreter.stdlib_path("{}.py".format(req))
            add_py_module = cls.needs_stdlib_py_module()
            if add_py_module is False:
                if module_path.exists():  # if present add it
                    add_py_module = True
                else:
                    add_py_module = not has_compile  # otherwise only add it if the pyc is not present
            if add_py_module:
                yield PathRefToDest(module_path, dest=cls.to_stdlib)

    @classmethod
    def needs_stdlib_py_module(cls):
        raise NotImplementedError

    def to_stdlib(self, src):
        return self.stdlib / src.name

    @classmethod
    def modules(cls):
        return []


def get_custom_site():
    return HERE / "site.py"
