from __future__ import absolute_import, unicode_literals

import logging
import os
from abc import ABCMeta

from six import add_metaclass

from virtualenv.util.path import Path
from virtualenv.util.zipapp import ensure_file_on_disk

from ..creator import Creator


@add_metaclass(ABCMeta)
class ViaGlobalRefApi(Creator):
    def __init__(self, options, interpreter):
        super(ViaGlobalRefApi, self).__init__(options, interpreter)
        self.symlinks = getattr(options, "copies", False) is False
        self.enable_system_site_package = options.system_site

    @classmethod
    def add_parser_arguments(cls, parser, interpreter, meta, app_data):
        super(ViaGlobalRefApi, cls).add_parser_arguments(parser, interpreter, meta, app_data)
        parser.add_argument(
            "--system-site-packages",
            default=False,
            action="store_true",
            dest="system_site",
            help="give the virtual environment access to the system site-packages dir",
        )
        group = parser.add_mutually_exclusive_group()
        if meta.can_symlink:
            group.add_argument(
                "--symlinks",
                default=True,
                action="store_true",
                dest="symlinks",
                help="try to use symlinks rather than copies, when symlinks are not the default for the platform",
            )
        if meta.can_copy:
            group.add_argument(
                "--copies",
                "--always-copy",
                default=not meta.can_symlink,
                action="store_true",
                dest="copies",
                help="try to use copies rather than symlinks, even when symlinks are the default for the platform",
            )

    def create(self):
        self.patch_distutils_via_pth()

    def patch_distutils_via_pth(self):
        """Patch the distutils package to not be derailed by its configuration files"""
        patch_file = Path(__file__).parent / "_distutils_patch_virtualenv.py"
        with ensure_file_on_disk(patch_file, self.app_data) as resolved_path:
            text = resolved_path.read_text()
        text = text.replace('"__SCRIPT_DIR__"', repr(os.path.relpath(str(self.script_dir), str(self.purelib))))
        patch_path = self.purelib / "_distutils_patch_virtualenv.py"
        logging.debug("add distutils patch file %s", patch_path)
        patch_path.write_text(text)

        pth = self.purelib / "_distutils_patch_virtualenv.pth"
        logging.debug("add distutils patch file %s", pth)
        pth.write_text("import _distutils_patch_virtualenv")

    def _args(self):
        return super(ViaGlobalRefApi, self)._args() + [("global", self.enable_system_site_package)]

    def set_pyenv_cfg(self):
        super(ViaGlobalRefApi, self).set_pyenv_cfg()
        self.pyenv_cfg["include-system-site-packages"] = "true" if self.enable_system_site_package else "false"
