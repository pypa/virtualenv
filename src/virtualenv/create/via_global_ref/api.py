from __future__ import absolute_import, unicode_literals

from abc import ABCMeta

from six import add_metaclass

from ..creator import Creator


@add_metaclass(ABCMeta)
class ViaGlobalRefApi(Creator):
    def __init__(self, options, interpreter):
        super(ViaGlobalRefApi, self).__init__(options, interpreter)
        self.symlinks = getattr(options, "copies", False) is False
        self.enable_system_site_package = options.system_site

    @classmethod
    def add_parser_arguments(cls, parser, interpreter, meta):
        super(ViaGlobalRefApi, cls).add_parser_arguments(parser, interpreter, meta)
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

    def _args(self):
        return super(ViaGlobalRefApi, self)._args() + [("global", self.enable_system_site_package)]

    def set_pyenv_cfg(self):
        super(ViaGlobalRefApi, self).set_pyenv_cfg()
        self.pyenv_cfg["include-system-site-packages"] = "true" if self.enable_system_site_package else "false"
