Skip an ``--extra-search-dir`` entry that is a file, such as a wheel, the same way a missing path is skipped. Seeding
used to fail with ``NotADirectoryError``, reported as a failure to download wheels.
