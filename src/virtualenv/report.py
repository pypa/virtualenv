from __future__ import absolute_import, unicode_literals

import logging
import sys

LEVELS = {
    0: logging.CRITICAL,
    1: logging.ERROR,
    2: logging.WARNING,
    3: logging.INFO,
    4: logging.DEBUG,
    5: logging.NOTSET,
}

MAX_LEVEL = max(LEVELS.keys())
LOGGER = logging.getLogger()


def setup_report(verbosity):
    _clean_handlers(LOGGER)
    if verbosity > MAX_LEVEL:
        verbosity = MAX_LEVEL  # pragma: no cover
    level = LEVELS[verbosity]
    msg_format = "%(message)s"
    if level >= logging.DEBUG:
        locate = "pathname" if level > logging.DEBUG else "module"
        msg_format += "[%(asctime)s] %(levelname)s [%({})s:%(lineno)d]".format(locate)

    formatter = logging.Formatter(str(msg_format))
    stream_handler = logging.StreamHandler(stream=sys.stdout)
    stream_handler.setLevel(level)
    LOGGER.setLevel(logging.NOTSET)
    stream_handler.setFormatter(formatter)
    LOGGER.addHandler(stream_handler)
    level_name = logging.getLevelName(level)
    logging.debug("setup logging to %s", level_name)


def _clean_handlers(log):
    for log_handler in list(log.handlers):  # remove handlers of libraries
        log.removeHandler(log_handler)
