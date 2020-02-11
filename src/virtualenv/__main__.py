from __future__ import absolute_import, print_function, unicode_literals

import argparse
import logging
import sys
from datetime import datetime


def run(args=None, options=None):
    start = datetime.now()
    from virtualenv.error import ProcessCallFailed
    from virtualenv.run import run_via_cli

    if args is None:
        args = sys.argv[1:]
    try:
        run_via_cli(args, options)
    except ProcessCallFailed as exception:
        print("subprocess call failed for {}".format(exception.cmd))
        print(exception.out, file=sys.stdout, end="")
        print(exception.err, file=sys.stderr, end="")
        raise SystemExit(exception.code)
    finally:
        logging.info("done in %.0fms", (datetime.now() - start).total_seconds() * 1000)


def run_with_catch(args=None):
    options = argparse.Namespace()
    try:
        run(args, options)
    except (KeyboardInterrupt, Exception) as exception:
        if options.with_traceback:
            logging.shutdown()  # force flush of log messages before the trace is printed
            raise
        else:
            logging.error("%s: %s", type(exception).__name__, exception)
            sys.exit(1)


if __name__ == "__main__":
    run_with_catch()
