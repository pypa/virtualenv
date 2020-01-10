from __future__ import absolute_import, unicode_literals

import abc
import json
import os

import six

from virtualenv.interpreters.create.support import Python2Supports
from virtualenv.interpreters.create.via_global_ref.via_global_self_do import ViaGlobalRefVirtualenvBuiltin
from virtualenv.util.path import Path, copy

HERE = Path(__file__).absolute().parent


@six.add_metaclass(abc.ABCMeta)
class Python2(ViaGlobalRefVirtualenvBuiltin, Python2Supports):
    def setup_python(self):
        super(Python2, self).setup_python()  # install the core first
        self.fixup_python2()  # now patch

    def fixup_python2(self):
        """Perform operations needed to make the created environment work on Python 2"""
        for module in self.modules():
            self.add_module(module)
        # 2. install a patched site-package, the default Python 2 site.py is not smart enough to understand pyvenv.cfg,
        # so we inject a small shim that can do this
        site_py = self.lib_dir / "site.py"
        relative_site_packages = [
            os.path.relpath(six.ensure_text(str(s)), six.ensure_text(str(site_py))) for s in self.site_packages
        ]
        site_py.write_text(
            get_custom_site().read_text().replace("___EXPECTED_SITE_PACKAGES___", json.dumps(relative_site_packages))
        )

    @abc.abstractmethod
    def modules(self):
        raise NotImplementedError

    def add_exe_method(self):
        return copy

    def add_module(self, req):
        for ext in ["py", "pyc"]:
            file_path = "{}.{}".format(req, ext)
            self.copier(self.system_stdlib / file_path, self.lib_dir / file_path)

    def add_folder(self, folder):
        self.copier(self.system_stdlib / folder, self.lib_dir / folder)


def get_custom_site():
    return HERE / "site.py"
