from __future__ import absolute_import, unicode_literals

import logging

from virtualenv.discovery.py_info import Cmd
from virtualenv.seed.embed.base_embed import BaseEmbed
from virtualenv.seed.embed.wheels.acquire import get_bundled_wheel_non_zipped, pip_wheel_env_run
from virtualenv.util.subprocess import Popen


class PipInvoke(BaseEmbed):
    def __init__(self, options):
        super(PipInvoke, self).__init__(options)

    def run(self, creator):
        cmd = self.get_pip_install_cmd(creator.exe, creator.interpreter.version_release_str)
        env = pip_wheel_env_run(creator.interpreter.version_release_str)
        logging.debug("pip seed by running: %s", Cmd(cmd, env))
        process = Popen(cmd, env=env)
        process.communicate()
        if process.returncode != 0:
            raise RuntimeError("failed seed")

    def get_pip_install_cmd(self, exe, version):
        cmd = [str(exe), "-m", "pip", "-q", "install", "--only-binary", ":all:"]
        for folder in {get_bundled_wheel_non_zipped(p, version).parent for p in self.packages}:
            cmd.extend(["--find-links", str(folder)])
            cmd.extend(self.extra_search_dir)
        if not self.download:
            cmd.append("--no-index")
        for key, version in self.package_version().items():
            cmd.append("{}{}".format(key, "=={}".format(version) if version is not None else ""))
        return cmd
