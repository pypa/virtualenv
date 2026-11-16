Honor ``VIRTUALENV_NO_DOWNLOAD=1`` and ``no_download = true``: the parser ignored both, so ``download = true`` in the
configuration file overrode the environment variable. The opt-out now wins when both flags are set at the same level, as
it does for ``--no-venv-redirect``.
