Make seeded pip launchers use the environment's filesystem path bytes in legacy POSIX locales. Both seeders now use a
shell wrapper when that path differs from its UTF-8 spelling. Launchers created by later pip installs are unaffected.
