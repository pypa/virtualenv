from __future__ import absolute_import, unicode_literals

from abc import ABCMeta, abstractmethod

import six


@six.add_metaclass(ABCMeta)
class Activator(object):
    def __init__(self, options):
        self.flag_prompt = options.prompt

    @classmethod
    def add_parser_arguments(cls, parser, interpreter):
        """add activator options"""

    @classmethod
    def supports(cls, interpreter):
        return True

    @abstractmethod
    def generate(self, creator):
        raise NotImplementedError
