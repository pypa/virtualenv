Make ``-p``/``--python`` and ``--try-first-with`` replace the interpreters set by ``VIRTUALENV_PYTHON``,
``VIRTUALENV_TRY_FIRST_WITH`` or the configuration file instead of being merged with them, so the configured interpreter
no longer wins over the one asked for and a ``-p`` that finds nothing fails instead of falling back to it. Try several
``VIRTUALENV_PYTHON`` values in the order given rather than starting with the second.
