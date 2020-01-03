from __future__ import absolute_import, unicode_literals

from virtualenv.seed.embed.base_embed import BaseEmbed
from virtualenv.seed.embed.wheels.acquire import get_bundled_wheel, pip_wheel_env_run
from virtualenv.util.subprocess import Popen


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
            cmd.extend(self.extra_search_dir)
        if not self.download:
            cmd.append("--no-index")
        for key, version in {"pip": self.pip_version, "setuptools": self.setuptools_version}.items():
            cmd.append("{}{}".format(key, "=={}".format(version) if version is not None else ""))

        process = Popen(cmd, env=pip_wheel_env_run(version))
        process.communicate()
