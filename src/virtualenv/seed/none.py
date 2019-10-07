from __future__ import absolute_import, unicode_literals

from virtualenv.seed.seeder import Seeder


class NoneSeeder(Seeder):
    @classmethod
    def add_parser_arguments(cls, parser):
        pass

    def run(self, creator):
        pass
