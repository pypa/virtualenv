from __future__ import absolute_import, print_function, unicode_literals

import logging
import os
import sys
from datetime import datetime

from virtualenv.config.cli.parser import VirtualEnvOptions
from virtualenv.util.six import ensure_text


def run(args=None, options=None):
    start = datetime.now()
    from virtualenv.error import ProcessCallFailed
    from virtualenv.run import cli_run

    if args is None:
        args = sys.argv[1:]
    try:
        session = cli_run(args, options)
        logging.warning(LogSession(session, start))
    except ProcessCallFailed as exception:
        print("subprocess call failed for {} with code {}".format(exception.cmd, exception.code))
        print(exception.out, file=sys.stdout, end="")
        print(exception.err, file=sys.stderr, end="")
        raise SystemExit(exception.code)


class LogSession(object):
    def __init__(self, session, start):
        self.session = session
        self.start = start

    def __str__(self):
        spec = self.session.creator.interpreter.spec
        elapsed = (datetime.now() - self.start).total_seconds() * 1000
        lines = [
            "created virtual environment {} in {:.0f}ms".format(spec, elapsed),
            "  creator {}".format(ensure_text(str(self.session.creator))),
        ]
        if self.session.seeder.enabled:
            lines += ("  seeder {}".format(ensure_text(str(self.session.seeder))),)
        if self.session.activators:
            lines.append("  activators {}".format(",".join(i.__class__.__name__ for i in self.session.activators)))
        return os.linesep.join(lines)


def run_with_catch(args=None):
    options = VirtualEnvOptions()
    try:
        run(args, options)
    except (KeyboardInterrupt, Exception) as exception:
        if getattr(options, "with_traceback", False):
            logging.shutdown()  # force flush of log messages before the trace is printed
            raise
        else:
            logging.error("%s: %s", type(exception).__name__, exception)
            sys.exit(1)


if __name__ == "__main__":
    run_with_catch()
