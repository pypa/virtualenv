``--upgrade-embed-wheels`` with read-only or temporary app-data now exits with status 1 after one error that asks for a
writable ``--app-data`` folder, instead of logging ``could not upgrade`` with an empty reason for every package and
Python version.
