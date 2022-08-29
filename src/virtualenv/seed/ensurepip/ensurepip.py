import logging
from subprocess import Popen

from virtualenv.discovery.cached_py_info import LogCmd
from virtualenv.seed.seeder import Seeder


class EnsurePipSeeder(Seeder):
    """A seeder that uses ensurepip."""

    def __init__(self, options):
        super().__init__(options, enabled=options.no_seed is False)

    @classmethod
    def add_parser_arguments(cls, parser, interpreter, app_data):  # noqa: U100
        pass

    def run(self, creator):
        cmd = [str(creator.exe), "-m", "ensurepip"]
        logging.debug("ensurepip seed by running: %s", LogCmd(cmd))
        process = Popen(cmd)
        process.communicate()
        if process.returncode != 0:
            raise RuntimeError(f"failed seed with ensurepip with code {process.returncode}")
