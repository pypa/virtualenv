from __future__ import absolute_import, print_function, unicode_literals

import sys

from virtualenv.error import ProcessCallFailed
from virtualenv.run import run_via_cli


def run(args=None):
    if args is None:
        args = sys.argv[1:]
    try:
        run_via_cli(args)
    except ProcessCallFailed as exception:
        print("subprocess call failed for {}".format(exception.cmd))
        print(exception.out, file=sys.stdout, end="")
        print(exception.err, file=sys.stderr, end="")
        raise SystemExit(exception.code)


if __name__ == "__main__":
    run()
