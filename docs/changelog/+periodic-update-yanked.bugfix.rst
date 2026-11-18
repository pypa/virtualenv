Stop seeding a release yanked from the package index once the next periodic update or ``--upgrade-embed-wheels`` runs.
The update reads yank flags from the simple API of the index ``pip`` is configured with: ``PIP_INDEX_URL``,
``PIP_EXTRA_INDEX_URL``, ``pip.conf``, credentials in the URL or ``.netrc``, ``cert`` and ``proxy``. An index that needs
keyring credentials or a client certificate keeps its logged releases.
