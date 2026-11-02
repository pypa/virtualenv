Reject a destination that already exists but is not a directory, such as ``/dev/null``, a FIFO or a socket, with a usage
error instead of a ``NotADirectoryError`` once creation has started. A regular file now gets the same message.
