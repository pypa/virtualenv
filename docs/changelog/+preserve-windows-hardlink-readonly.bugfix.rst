Keep the read-only attribute of surviving Windows hard links when replacing or clearing an environment. On filesystems
that reject attribute-preserving deletion, refuse to remove a read-only hard link. Restore Windows support for PyPy 3.9,
where importing the directory junction tag from :mod:`stat` failed.
