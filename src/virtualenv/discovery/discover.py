from __future__ import absolute_import, unicode_literals

from abc import ABCMeta, abstractmethod

import six


@six.add_metaclass(ABCMeta)
class Discover(object):
    def __init__(self):
        self._has_run = False
        self._interpreter = None

    @classmethod
    def add_parser_arguments(cls, parser):
        raise NotImplementedError

    @abstractmethod
    def run(self):
        raise NotImplementedError

    @property
    def interpreter(self):
        if self._has_run is False:
            self._interpreter = self.run()
            self._has_run = True
        return self._interpreter
