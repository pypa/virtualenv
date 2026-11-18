Stop the ``bash``, ``csh`` and PowerShell activators from adding an empty entry when ``PATH`` is empty. On POSIX an
empty entry searches the current directory, so activating with an empty ``PATH`` put it on the search path.
