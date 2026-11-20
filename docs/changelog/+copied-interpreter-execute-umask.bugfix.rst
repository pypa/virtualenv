The builtin creator preserves the permissions set when it copies an interpreter and its aliases. On POSIX, a default ACL
on the destination directory controls access where present. Otherwise the process umask applies.
