Preserve custom ``histchars`` when sourcing ``activate.csh``. The script now reads its generated literals with the
default history character, so a custom setting cannot reinterpret a prompt or path as shell syntax.
