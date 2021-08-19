from __future__ import absolute_import, unicode_literals

import pytest

from virtualenv.activation import NushellActivator, nushell
from virtualenv.info import IS_WIN


# @pytest.mark.skipif(IS_WIN, reason="Github Actions ships with WSL bash")
def test_nushell(activation_tester_class, activation_tester):
    class Nushell(activation_tester_class):
        def __init__(self, session):
            cmd = "C:\\Users\Benzaa\\Documents\\cargo-target\\debug\\nu"
            # cmd = "nu"
            super(Nushell, self).__init__(NushellActivator, session, cmd, "activate.nu", "nu")
            self.activate_cmd = "source"

            deactivate = session.creator.dest / session.creator.bin_dir / "deactivate.nu"
            self.deactivate = "source '{}'".format(deactivate)

    activation_tester(Nushell)


# @elferherrera You could use this to get the name of the latest release
# tarball: curl -s https://api.github.com/repos/nushell/nushell/releases/latest | grep 'browser_' | cut -d\" -f4 | grep .tar.gz.
# You call wget $(curl ...) to actually download it.
# Source: https://stackoverflow.com/questions/24085978/github-url-for-latest-release-of-the-download-file
