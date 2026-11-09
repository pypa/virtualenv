Honor ``VIRTUALENV_NO_DOWNLOAD=1`` and ``no_download = true``: the parser read them as enabling the download and let
``download = true`` in the configuration file override the environment variable. The opt-out now wins when both flags
are set at the same level, as it does for ``--no-venv-redirect``.
