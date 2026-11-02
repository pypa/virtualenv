Treat an empty ``VIRTUALENV_OVERRIDE_APP_DATA`` or ``VIRTUALENV_CONFIG_FILE`` as unset, as virtualenv already does for
its option variables. An empty app-data override made the current directory the cache, so ``--reset-app-data`` deleted
it, and an empty config file path logged an error on every run.
