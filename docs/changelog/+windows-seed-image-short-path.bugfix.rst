Fix seeding from a deep ``--app-data`` folder on Windows without long path support, which failed with ``WinError 206``
or ``WinError 3``. The check for whether the seed wheel image needs its 8.3 short path now counts the separator and the
248 character limit on directories, and the install reads the image through its short path whether it was just built or
reused from an earlier run.
