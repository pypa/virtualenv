import click

import virtualenv


@click.command(
    context_settings={
        "help_option_names": ["-h", "--help"],
    },
    epilog=(
        "Once an environment has been created, you may wish to activate it by "
        "sourcing an activate script in its bin directory."
    ),
)
@click.version_option(version=virtualenv.__version__)
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
    pass
