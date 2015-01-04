from __future__ import absolute_import, division, print_function

import os
import sys

from virtualenv.builders.legacy import LegacyBuilder
from virtualenv.builders.venv import VenvBuilder
from virtualenv.flavors.posix import PosixFlavor
from virtualenv.flavors.windows import WindowsFlavor


def select_flavor():
    # Determine if we're running under Windows or not.
    if (sys.platform.startswith("win")
            or (sys.platform == "cli" and os.name == "nt")):
        return WindowsFlavor

    return PosixFlavor


def select_builder(python, builders=None):
    # Determine what Python we're going to be using. If this is None we'll use
    # the Python which we're currently running under.
    if python is None:
        python = sys.executable

    # If we were not given a list of builders we'll default to one that
    # contains both of our builders
    if builders is None:
        builders = [VenvBuilder, LegacyBuilder]

    # Loop over our builders and return the first one that is acceptable for
    # the target Python.
    for builder in builders:
        if builder.check_available(python):
            return builder

    # If we got to this point then we haven't selected a builder then we need
    # to raise an error.
    raise RuntimeError("No available builders for the target Python.")


def create(destination, python=None, **kwargs):
    # Determine which builder to use based on the capabiltiies of the target
    # python.
    builder_type = select_builder(python)

    # Determine which flavor to use, based on the platform we're running on.
    flavor_type = select_flavor()

    # Instantiate our selected builder with the values given to us, and then
    # create our virtual environment using the given builder.
    builder = builder_type(python=python, flavor=flavor_type(), **kwargs)
    builder.create(destination)
