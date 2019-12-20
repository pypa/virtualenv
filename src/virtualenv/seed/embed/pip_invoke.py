from __future__ import absolute_import, unicode_literals

import os
import subprocess

from virtualenv.seed.embed.base_embed import BaseEmbed
from virtualenv.seed.embed.wheels.acquire import get_bundled_wheel


class PipInvoke(BaseEmbed):
    def __init__(self, options):
        super(PipInvoke, self).__init__(options)

    def run(self, creator):
        if not self.enabled:
            return

        version = creator.interpreter.version_release_str

        cmd = [str(creator.exe), "-m", "pip", "install", "--only-binary", ":all:"]
        for folder in {get_bundled_wheel(p, version).parent for p in ("pip", "setuptools")}:
            cmd.extend(["--find-links", str(folder)])
        if not self.download:
            cmd.append("--no-index")
        for key, version in {"pip": self.pip_version, "setuptools": self.setuptools_version}.items():
            cmd.append("{}{}".format(key, "=={}".format(version) if version is not None else ""))

        env = os.environ.copy()
        env.update(
            {
                str(k): str(v)  # python 2 requires these to be string only (non-unicode)
                for k, v in {
                    # put the bundled wheel onto the path, and use it to do the bootstrap operation
                    "PYTHONPATH": get_bundled_wheel("pip", version),
                    "PIP_USE_WHEEL": "1",
                    "PIP_USER": "0",
                    "PIP_NO_INPUT": "1",
                }.items()
            }
        )

        subprocess.call(cmd, env=env)
