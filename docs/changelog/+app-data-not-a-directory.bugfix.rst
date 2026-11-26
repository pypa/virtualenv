Reject an explicit ``--app-data`` path that exists but is not a directory, instead of failing later with a
``NotADirectoryError`` while seeding; a path taken from ``VIRTUALENV_OVERRIDE_APP_DATA`` that is not a directory now
warns and falls back to temporary app-data.
