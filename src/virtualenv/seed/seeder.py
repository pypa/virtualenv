from __future__ import absolute_import, unicode_literals

from abc import ABCMeta, abstractmethod

import six


@six.add_metaclass(ABCMeta)
class Seeder(object):
    def __init__(self, options, enabled):
        self.enabled = enabled

    @classmethod
    def add_parser_arguments(cls, parser, interpreter):
        raise NotImplementedError

    @abstractmethod
    def run(self, creator):
        raise NotImplementedError
