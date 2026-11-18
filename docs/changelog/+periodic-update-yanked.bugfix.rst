Stop seeding a release yanked from the package index once the next periodic update or ``--upgrade-embed-wheels`` runs.
The yank flags come from the index ``pip`` is configured with, so an index that needs keyring credentials or a client
certificate keeps its logged releases.
