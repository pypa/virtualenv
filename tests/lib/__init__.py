import os
import subprocess

import pytest

IS_INSIDE_CI = "CI_RUN" in os.environ


def need_executable(name, check_cmd):
    """skip running this locally if executable not found, unless we're inside the CI"""

    def wrapper(fn):
        fn = getattr(pytest.mark, name)(fn)
        if IS_INSIDE_CI:
            return fn
        try:
            subprocess.check_output(check_cmd)
        except OSError:
            return pytest.mark.skip(reason="{} is not available".format(name))(fn)
        return fn

    return wrapper
