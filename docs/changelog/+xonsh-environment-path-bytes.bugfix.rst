Keep Xonsh activation on the created environment when the sourcing session uses a different filesystem codec. For
non-ASCII POSIX destinations, the script now records UTF-8 path bytes and decodes them in the sourcing session, so
``VIRTUAL_ENV``, ``PATH``, and ``PKG_CONFIG_PATH`` retain the original path bytes. If the codec cannot represent the new
environment, the current environment stays active.
