Report why a read-only app data folder cannot keep an embed update log, instead of failing with an empty reason:
``virtualenv --read-only-app-data --upgrade-embed-wheels`` now prints ``could not upgrade pip for python 3.12: read-only
app data does not keep an embed update log`` rather than a bare ``could not upgrade pip for python 3.12:``.
