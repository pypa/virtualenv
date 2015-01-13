from __future__ import absolute_import, division, print_function

import subprocess
import textwrap

from virtualenv._compat import check_output
from virtualenv.builders.base import BaseBuilder


_SCRIPT = """
import venv

# Create our actual builder with our settings.
builder = venv.EnvBuilder(
    system_site_packages={system_site_packages!r},
    symlinks=False,
)

# Make sure that pip is actually disabled.
builder.with_pip = False

# Don't install the activate scripts, we'll want to install our own
# instead.
builder.install_scripts = lambda *a, **kw: None

# Create the virtual environment.
builder.create({destination!r})
"""


class VenvBuilder(BaseBuilder):

    @classmethod
    def check_available(cls, python):
        try:
            check_output([
                # Bail if any Python has be Debian-ized: venv is broken beyond any workaround we can do here - resulting
                # venvs will use "local/lib" instead of "lib" and have "dist-packages" instead of "site-packages"
                # TODO: report this terrible mess upstream
                python,
                "-c",
                textwrap.dedent("""
                import venv
                from sysconfig import get_scheme_names
                from distutils.command.install import INSTALL_SCHEMES

                if 'posix_local' in sysconfig.get_scheme_names() or 'deb_system' in INSTALL_SCHEMES:
                    raise RuntimeError("there are Debian patches")
                """)
            ], stderr=subprocess.STDOUT)
        except subprocess.CalledProcessError:
            return False
        else:
            return True

    def create_virtual_environment(self, destination):
        # Create our script using our template and the given settings for
        # this environment.
        script = _SCRIPT.format(
            system_site_packages=self.system_site_packages,
            destination=destination,
        )

        # Subshell into the venv module and create a new virtual environment.
        # We use the programatic API instead of the command line because we
        # want to not include pip in this, and Python 3.3's venv module doesn't
        # support the --without-pip flag.
        subprocess.check_call([self._python_bin, "-c", script])
