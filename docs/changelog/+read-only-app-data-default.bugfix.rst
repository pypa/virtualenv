Build the default application data folder only when no folder was given through ``--app-data``, ``VIRTUALENV_APP_DATA``
or the configuration file, so ``--read-only-app-data`` with an explicit folder works when the default folder is missing,
and writable runs stop creating an unused one. Folders from ``VIRTUALENV_APP_DATA`` and the configuration file now get
the same checks as ``--app-data``.
