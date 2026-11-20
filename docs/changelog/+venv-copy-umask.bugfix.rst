Apply file-creation permissions, including default ACLs, to interpreters copied by the stdlib ``venv`` creator. Shared
directories retain their mode unless the copy needs temporary protection. Linux runtimes with default ACL lookup can
restore owner execute when the umask alone removes it.
