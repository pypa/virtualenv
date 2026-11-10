Count the path separator and the 248 character limit on directories when deciding whether a seed wheel image needs its
Windows short path, and read the image through that short path on every run rather than only while building it. Without
long path support, a deep ``--app-data`` folder failed with ``WinError 206``, or with ``WinError 3`` from the second run
on.
