Skip empty configured search directory entries instead of searching the current working directory. Reject an empty
``--extra-search-dir`` command-line value. Empty ``--python`` and ``--try-first-with`` items from environment variables
or the config file are skipped too, so they no longer select the running interpreter.
