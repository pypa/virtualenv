Reject an empty or whitespace-only destination instead of resolving it to the current directory, so an unset ``VENV`` in
``virtualenv --clear "$VENV"`` no longer deletes the working directory. Pass ``.`` to create the environment in the
current directory.
