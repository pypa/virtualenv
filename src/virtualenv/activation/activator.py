from __future__ import absolute_import, unicode_literals

from abc import ABCMeta, abstractmethod

import six


@six.add_metaclass(ABCMeta)
class Activator(object):
    def __init__(self, options):
        self.flag_prompt = options.prompt

    @classmethod
    def add_parser_arguments(cls, parser):
        pass

    def run(self, creator):
        self.generate()
        if self.flag_prompt is not None:
            creator.pyenv_cfg["prompt"] = self.flag_prompt

    @abstractmethod
    def generate(self):
        raise NotImplementedError
