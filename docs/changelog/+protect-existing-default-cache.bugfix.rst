Make existing default app-data cache roots owner-only on POSIX. Setgid roots keep their group permissions but lose other
access. Restore those modes after ``--reset-app-data``.
