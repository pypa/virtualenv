Match a pinned seed version such as ``--pip 26.3.0`` or ``--pip v26.3`` against the bundled, cached or extra search dir
wheel by PEP 440 equality rather than by exact string. A spelling that differs from the wheel filename skipped the
bundled wheel and downloaded the same release from PyPI, even under ``--no-download``, so it failed offline.
