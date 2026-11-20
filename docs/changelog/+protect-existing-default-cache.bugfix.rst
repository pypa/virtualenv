Make existing default app-data cache roots owner-only on POSIX. Setgid roots keep their group permissions but lose other
access. Restore those modes after ``--reset-app-data``. Skip default caches owned by another non-root user, including
during migration and in read-only mode. An explicit ``--app-data`` path keeps its own ownership policy.
