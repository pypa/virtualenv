Stop the target debug report (``-vv`` and ``Creator.debug``) from dropping the first real ``sys.path`` entry when
``PYTHONSAFEPATH`` is set. The report removes the debug script's directory, which safe-path mode never adds.
