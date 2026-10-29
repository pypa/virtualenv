Reject an empty or whitespace-only destination. An empty one, and on Windows one made only of spaces, resolved to the
current directory, so an unset ``VENV`` in ``virtualenv --clear "$VENV"`` deleted the working directory. Pass ``.`` to
create the environment in the current directory.
