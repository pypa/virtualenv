from __future__ import absolute_import, unicode_literals

from virtualenv.discovery import CURRENT
from virtualenv.run import run_via_cli
from virtualenv.seed.wheels import BUNDLE_SUPPORT

dest = r"C:\Users\traveler\git\virtualenv\test\unit\interpreters\boostrap\perf"
bundle_ver = BUNDLE_SUPPORT[CURRENT.version_release_str]
cmd = [
    dest,
    "--download",
    "--pip",
    bundle_ver["pip"].split("-")[1],
    "--setuptools",
    bundle_ver["setuptools"].split("-")[1],
]
result = run_via_cli(cmd)
assert result
