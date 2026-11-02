Add the environment's ``lib/pkgconfig`` to ``PKG_CONFIG_PATH`` when activating from xonsh, and restore the previous
value or unset it again on ``deactivate``, as the other activators already do.
