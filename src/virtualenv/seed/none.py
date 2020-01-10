from __future__ import absolute_import, unicode_literals

from virtualenv.seed.seeder import Seeder


class NoneSeeder(Seeder):
    def __init__(self, options):
        super(NoneSeeder, self).__init__(options, False)

    @classmethod
    def add_parser_arguments(cls, parser, interpreter):
        pass

    def run(self, creator):
        pass
