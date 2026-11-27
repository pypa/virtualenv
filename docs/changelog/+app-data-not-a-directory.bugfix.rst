An explicit ``--app-data`` path that exists but is not a directory is now a usage error. When
``VIRTUALENV_OVERRIDE_APP_DATA`` or the default cache names such a path, writable runs warn and use temporary app-data
instead of failing while seeding, and a file at the default cache location keeps its permissions.
