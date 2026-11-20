Apply the current umask to interpreters copied by the stdlib ``venv`` creator. When reusing an environment, restrict
access to its ``bin`` directory during creation, then restore the directory's previous mode after narrowing new files.
