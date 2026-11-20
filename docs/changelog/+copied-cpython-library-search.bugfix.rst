Reject CPython 3.14+ copy-mode environments when a sibling standard-library search location can be changed by another
account or already contains a zip that would replace the host standard library. The ``libpython`` copy remains for
builds that need it to start the copied interpreter.
