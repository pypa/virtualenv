Fix ``--reset-app-data`` on a deep app data folder on Windows without long path support. It failed with ``WinError 145``
after deleting only part of the seed ``pip`` image, so later runs seeded a ``pip`` that could not be imported. Folders
holding files past the 260 character path limit are now deleted in full, so a run also cleans up the staging folder a
killed seed image build leaves behind, instead of failing until the app data is cleared by hand.
