from __future__ import absolute_import, unicode_literals

import logging
import sys

from virtualenv.discovery.cached_py_info import LogCmd
from virtualenv.seed.embed.base_embed import BaseEmbed
from virtualenv.util.path import path_accessor
from virtualenv.util.subprocess import Popen

from ..wheels import Version, get_wheel, pip_wheel_env_run

if sys.version_info >= (3, 3):
    from contextlib import ExitStack, contextmanager
else:
    from contextlib2 import ExitStack, contextmanager


class PipInvoke(BaseEmbed):
    def __init__(self, options):
        super(PipInvoke, self).__init__(options)

    def run(self, creator):
        if not self.enabled:
            return
        for_py_version = creator.interpreter.version_release_str
        with self.get_pip_install_cmd(creator.exe, for_py_version) as cmd:
            env = pip_wheel_env_run(self.extra_search_dir, self.app_data, self.env)
            self._execute(cmd, env)

    @staticmethod
    def _execute(cmd, env):
        logging.debug("pip seed by running: %s", LogCmd(cmd, env))
        process = Popen(cmd, env=env)
        process.communicate()
        if process.returncode != 0:
            raise RuntimeError("failed seed with code {}".format(process.returncode))
        return process

    @contextmanager
    def get_pip_install_cmd(self, exe, for_py_version):
        cmd = [str(exe), "-m", "pip", "-q", "install", "--only-binary", ":all:", "--disable-pip-version-check"]
        if not self.download:
            cmd.append("--no-index")
        folders = set()
        with ExitStack() as stack:
            for dist, version in self.distribution_to_versions().items():
                wheel = get_wheel(
                    distribution=dist,
                    version=version,
                    for_py_version=for_py_version,
                    search_dirs=self.extra_search_dir,
                    download=False,
                    app_data=self.app_data,
                    do_periodic_update=self.periodic_update,
                    env=self.env,
                )
                if wheel is None:
                    raise RuntimeError("could not get wheel for distribution {}".format(dist))
                stack.enter_context(path_accessor(wheel.path))
                folders.add(str(wheel.path.parent))
                cmd.append(Version.as_pip_req(dist, wheel.version))
            for folder in sorted(folders):
                cmd.extend(["--find-links", str(folder)])
            yield cmd
