Restore the interpreter search path check for copied POSIX CPython environments created with the stdlib venv creator. An
unsafe search path stops creation before ``--clear`` removes the existing environment.
