Reject an empty or whitespace-only ``--app-data``, and a whitespace-only ``VIRTUALENV_APP_DATA``. An empty one, and on
Windows one made only of spaces, made the current directory the cache, so ``--reset-app-data`` deleted it.
