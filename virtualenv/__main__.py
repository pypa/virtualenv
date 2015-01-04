from __future__ import absolute_import, division, print_function

from functools import partial

from virtualenv.core import cli


main = partial(cli, prog_name="virtualenv")

if __name__ == "__main__":
    main()
