Create environments from the zipapp with ``--read-only-app-data`` when the app data already holds the seed wheels.
Making the embedded wheels available tried to create a lock file in the read-only wheel folder, so seeding failed with a
``PermissionError``.
