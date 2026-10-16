Detach seed-package and launcher symlinks before running the pip seeder. Reseeding an environment created with
``--symlink-app-data`` no longer rewrites its shared wheel image. Unrelated launcher symlinks remain in place.

Preserve case in console entry-point names and use the last value for duplicate entries when regenerating launchers.

Remove linked metadata from previous seed versions when reseeding with pip so package listings report the installed
version.
