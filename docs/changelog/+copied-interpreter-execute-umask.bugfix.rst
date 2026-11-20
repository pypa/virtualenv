Keep copied interpreters and their aliases within the current umask. The copy step already applies the umask, but a
later permission change restored execute bits that the umask had removed.
