from __future__ import absolute_import, unicode_literals

import json
import logging


class Session(object):
    def __init__(self, verbosity, interpreter, creator, seeder, activators):
        self.verbosity = verbosity
        self.interpreter = interpreter
        self.creator = creator
        self.seeder = seeder
        self.activators = activators

    def run(self):
        self._create()
        self._seed()
        self._activate()
        self.creator.pyenv_cfg.write()

    def _create(self):
        self.creator.run()
        logging.debug(_DEBUG_MARKER)
        logging.debug("%s", _Debug(self.creator))

    def _seed(self):
        if self.seeder is not None:
            self.seeder.run(self.creator)

    def _activate(self):
        for activator in self.activators:
            activator.generate(self.creator)


_DEBUG_MARKER = "=" * 30 + " target debug " + "=" * 30


class _Debug(object):
    """lazily populate debug"""

    def __init__(self, creator):
        self.creator = creator

    def __str__(self):
        return json.dumps(self.creator.debug, indent=2)
