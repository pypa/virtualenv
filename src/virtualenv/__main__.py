from __future__ import absolute_import, print_function, unicode_literals

import argparse
import logging
import sys
from datetime import datetime

import six


def run(args=None, options=None):
    start = datetime.now()
    from virtualenv.error import ProcessCallFailed
    from virtualenv.run import cli_run

    if args is None:
        args = sys.argv[1:]
    try:
        session = cli_run(args, options)
        logging.warning(
            "created virtual environment in %.0fms %s with seeder %s",
            (datetime.now() - start).total_seconds() * 1000,
            six.ensure_text(str(session.creator)),
            six.ensure_text(str(session.seeder)),
        )
    except ProcessCallFailed as exception:
        print("subprocess call failed for {}".format(exception.cmd))
        print(exception.out, file=sys.stdout, end="")
        print(exception.err, file=sys.stderr, end="")
        raise SystemExit(exception.code)


def run_with_catch(args=None):
    options = argparse.Namespace()
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
