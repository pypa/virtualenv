On POSIX, the builtin creator honors the destination directory's default ACL when copying interpreters and aliases.
Without a default ACL the umask controls group and other access. If the copy lacks owner execute permission, virtualenv
restores it on Linux when the directory has no default ACL. Otherwise creation fails with a hint to use ``--symlinks``.
