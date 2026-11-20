Keep Xonsh activation on the created environment when the sourcing session uses a different filesystem codec. The script
now records the environment path as UTF-8 bytes and decodes them in the sourcing session, so ``VIRTUAL_ENV``, ``PATH``,
and ``PKG_CONFIG_PATH`` retain the original path bytes.
