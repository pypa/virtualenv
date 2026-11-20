Apply file-creation permissions, including default ACLs, to interpreters copied by the stdlib ``venv`` creator. Shared
directories retain their mode unless the copy needs temporary protection. On Linux, the interpreter remains executable
by its owner when the umask alone removes owner execute.
