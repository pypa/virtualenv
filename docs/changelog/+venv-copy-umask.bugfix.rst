Apply the current umask to interpreters copied by the stdlib ``venv`` creator. Restrict access to ``bin`` during
creation, then restore the directory's previous mode after narrowing new files.
