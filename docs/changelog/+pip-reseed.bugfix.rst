Detach seed-package and launcher symlinks before running the pip seeder. Reseeding an environment created with
``--symlink-app-data`` no longer rewrites its shared wheel image. Unrelated launcher symlinks remain in place.
