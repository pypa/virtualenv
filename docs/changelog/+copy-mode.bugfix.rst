Apply the current umask when copying interpreter and seed-package files instead of inheriting cached permission bits.
Executable sources remain executable within the permissions allowed by that umask.
