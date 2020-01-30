from __future__ import absolute_import, print_function, unicode_literals

import logging
import sys
from datetime import datetime


def run(args=None):
    start = datetime.now()
    from virtualenv.error import ProcessCallFailed
    from virtualenv.run import run_via_cli

    if args is None:
        args = sys.argv[1:]
    try:
        run_via_cli(args)
    except ProcessCallFailed as exception:
        print("subprocess call failed for {}".format(exception.cmd))
        print(exception.out, file=sys.stdout, end="")
        print(exception.err, file=sys.stderr, end="")
        raise SystemExit(exception.code)
    finally:
        logging.info("done in %.0fms", (datetime.now() - start).total_seconds() * 1000)


def run_with_catch(args=None):
    try:
        run(args)
    except (KeyboardInterrupt, Exception) as exception:
        logging.error("%s: %s", type(exception).__name__, exception)
        sys.exit(1)


if __name__ == "__main__":
    run_with_catch()
