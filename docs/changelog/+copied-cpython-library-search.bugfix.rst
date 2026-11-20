Both POSIX creators check the standard-library search paths of shared CPython 3.11+ builds when using ``--copies``. They
reject unsafe library directories and unexpected standard-library zips, and warn when another account could change a
search directory after creation. Use ``--symlinks`` or a private parent directory to avoid that risk.
