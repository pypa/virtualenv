Apply file-creation permissions, including default ACLs, to interpreters copied by the stdlib ``venv`` creator. Limit
access to ``bin`` during creation, then restore the directory's previous mode after narrowing new files.
