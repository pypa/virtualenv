Reject ``--clear`` when the destination itself is a symlink. Pass the target directory explicitly to clear it. Creating
an environment through a symlink without ``--clear`` remains supported.
