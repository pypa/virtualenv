from __future__ import absolute_import, unicode_literals

import abc
import json
import os

import six

from virtualenv.create.describe import Python2Supports
from virtualenv.create.via_global_ref.builtin.ref import PathRefToDest
from virtualenv.info import IS_ZIPAPP
from virtualenv.util.path import Path
from virtualenv.util.zipapp import read as read_from_zipapp

from ..via_global_self_do import ViaGlobalRefVirtualenvBuiltin

HERE = Path(os.path.abspath(__file__)).parent


@six.add_metaclass(abc.ABCMeta)
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
        expected = json.dumps(
            [os.path.relpath(six.ensure_text(str(i)), six.ensure_text(str(site_py))) for i in self.libs]
        )
        site_py.write_text(custom_site_text.replace("___EXPECTED_SITE_PACKAGES___", expected))

    @classmethod
    def sources(cls, interpreter):
        for src in super(Python2, cls).sources(interpreter):
            yield src
        # install files needed to run site.py
        for req in cls.modules():
            yield PathRefToDest(Path(interpreter.system_stdlib) / "{}.py".format(req), dest=cls.to_stdlib)
            comp = Path(interpreter.system_stdlib) / "{}.pyc".format(req)
            if comp.exists():
                yield PathRefToDest(comp, dest=cls.to_stdlib)

    def to_stdlib(self, src):
        return self.stdlib / src.name

    @classmethod
    def modules(cls):
        return []


def get_custom_site():
    return HERE / "site.py"
