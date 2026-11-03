Treat an empty or blank ``VIRTUALENV_OVERRIDE_APP_DATA`` and an empty ``VIRTUALENV_CONFIG_FILE`` as unset, as virtualenv
already does for its option variables. An empty app-data override, or on Windows one made of spaces, made the current
directory the cache, so ``--reset-app-data`` deleted it, and an empty config file path logged an error on every run.
