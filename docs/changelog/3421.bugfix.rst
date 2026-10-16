Restrict the default app-data directory to its owner on POSIX, including existing caches. Explicit app-data paths keep
their permissions so shared caches remain usable. Use temporary app-data if default cache permissions cannot be set.
