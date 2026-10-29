On Windows, re-create an environment in place when its copied interpreter files, such as ``python.exe``, are read-only,
instead of failing with ``PermissionError``. A read-only hard link is left alone and reported, since clearing the
attribute would change the file's other names too.
