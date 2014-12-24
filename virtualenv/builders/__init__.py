import subprocess
import sys

from virtualenv.builders.legacy import LegacyBuilder
from virtualenv.builders.venv import VenvBuilder


def select_builder(python):
    # Determine what Python we're going to be using. If this is None we'll use
    # the Python which we're currently running under.
    if python is None:
        python = sys.executable

    # Determine if the target Python supports the venv module or not.
    try:
        subprocess.check_output(
            [python, "-c", "import venv"],
            stderr=subprocess.STDOUT,
        )
    except subprocess.CalledProcessError:
        return LegacyBuilder
    else:
        return VenvBuilder
