Run the interpreter that collects the target debug information (``-vv`` output and ``Creator.debug``) without
``PYTHONPATH`` and with the environment passed to ``cli_run``, so the reported ``sys.path`` no longer lists the caller's
``PYTHONPATH`` entries.
