Make ``virtualenv --upgrade-embed-wheels`` exit with status ``1`` and log one ``could not upgrade`` error per
distribution when an upgrade fails, instead of printing a thread traceback for each and exiting with ``0``.
