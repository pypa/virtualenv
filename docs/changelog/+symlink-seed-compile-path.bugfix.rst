On Windows, include bytecode cache directories and temporary bytecode files when checking whether ``--symlink-app-data``
needs the seed image's 8.3 short path. This lets virtualenv build seed images when the wheel files fit within the legacy
path limit and bytecode compilation needs more room.
