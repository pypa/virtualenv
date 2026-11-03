Read ``virtualenv.ini`` values without interpolation, as environment variables and command line flags already are. A
value holding a ``%``, such as ``prompt = 50% done``, was ignored without any message. ``%%`` and ``%(name)s`` are now
kept as written, so write a single ``%``.
