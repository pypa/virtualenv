On Windows, re-create an environment in place when its copied interpreter files, such as ``python.exe``, or its seeded
packages are read-only, instead of failing with ``PermissionError``.
