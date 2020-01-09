from __future__ import absolute_import, unicode_literals

import json
import logging

import six


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
        logging.info("create virtual environment via %s", six.ensure_text(str(self.creator)))
        self.creator.run()
        logging.debug(_DEBUG_MARKER)
        logging.debug("%s", _Debug(self.creator))

    def _seed(self):
        if self.seeder is not None and self.seeder.enabled:
            logging.info("add seed packages via %s", self.seeder)
            self.seeder.run(self.creator)

    def _activate(self):
        if self.activators:
            logging.info(
                "add activators for %s", ", ".join(type(i).__name__.replace("Activator", "") for i in self.activators)
            )
            for activator in self.activators:
                activator.generate(self.creator)


_DEBUG_MARKER = "=" * 30 + " target debug " + "=" * 30


class _Debug(object):
    """lazily populate debug"""

    def __init__(self, creator):
        self.creator = creator

    def __unicode__(self):
        return six.ensure_text(repr(self))

    def __repr__(self):
        return json.dumps(self.creator.debug, indent=2)
