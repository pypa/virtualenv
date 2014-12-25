import subprocess
import sys

import click

from virtualenv import __version__
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


def create(destination, python=None, **kwargs):
    # Determine which builder to use based on the capabiltiies of the target
    # python.
    builder_type = select_builder(python)

    # Instantiate our selected builder with the values given to us, and then
    # create our virtual environment using the given builder.
    builder = builder_type(python=python, **kwargs)
    builder.create(destination)


@click.command(
    context_settings={
        "help_option_names": ["-h", "--help"],
    },
    epilog=(
        "Once an environment has been created, you may wish to activate it by "
        "sourcing an activate script in its bin directory."
    ),
)
@click.version_option(version=__version__)
@click.option("-v", "--verbose", count=True, help="Increase verbosity.")
@click.option("-q", "--quiet", count=True, help="Decrease verbosity.")
@click.option(
    "-p", "--python",
    help=(
        "The Python interpreter to use in the newly created virtual "
        "environment."
    ),
)
@click.option(
    "--clear",
    is_flag=True,
    help="Clear out the virtual environment and start from scratch.",
)
@click.option(
    "--system-site-packages/--no-site-packages",
    default=False,
    help="Give the virtual environment access to the global site-packages.",
)
@click.option(
    "--always-copy",
    is_flag=True, help="Always copy files rather than symlinking.",
)
@click.option(
    "--relocatable",
    is_flag=True,
    help=(
        "Make an EXISTING virtualenv environment relocatable. This fixes up "
        "scripts and makes all .pth files relative."
    ),
)
@click.option(
    "--setuptools/--no-setuptools",
    default=True,
    help="Install setuptools into the new virtual environment.",
)
@click.option(
    "--pip/--no-pip",
    default=True,
    help="Install pip into the new virtual environment.",
)
@click.option(
    "--extra-search-dir",
    multiple=True,
    help=(
        "Directory to look for setuptools/pip distributions in. This option "
        "can be used multiple times."
    ),
)
@click.option(
    "--prompt",
    help="Provides an alternative prompt prefix for this environment.",
)
@click.argument("destination")
def cli(destination,
        verbose=0,
        quiet=0,
        python=None,
        system_site_packages=False,
        clear=False,
        always_copy=False,
        prompt=None,
        relocatable=False,
        extra_search_dir=None,
        pip=True,
        setuptools=True):
    """
    Creates virtual python environments in a target directory.
    """

    create(
        destination,
        python=python,
        system_site_packages=system_site_packages,
        clear=clear,
        pip=pip,
        setuptools=setuptools,
        extra_search_dirs=extra_search_dir,
    )
