from __future__ import absolute_import, unicode_literals

from abc import ABCMeta

from six import add_metaclass

from .creator import Creator


@add_metaclass(ABCMeta)
class ViaGlobalRef(Creator):
    def __init__(self, options, interpreter):
        super(ViaGlobalRef, self).__init__(options, interpreter)
        self.symlinks = options.symlinks

    @classmethod
    def add_parser_arguments(cls, parser, interpreter):
        super(ViaGlobalRef, cls).add_parser_arguments(parser, interpreter)
        group = parser.add_mutually_exclusive_group()
        symlink = False if interpreter.os == "nt" else True
        group.add_argument(
            "--symlinks",
            default=symlink,
            action="store_true",
            dest="symlinks",
            help="Try to use symlinks rather than copies, when symlinks are not the default for the platform.",
        )
        group.add_argument(
            "--copies",
            "--always-copy",
            default=not symlink,
            action="store_false",
            dest="symlinks",
            help="Try to use copies rather than symlinks, even when symlinks are the default for the platform.",
        )
