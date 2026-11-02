Read ``virtualenv.ini`` values as written, as environment variables and command line flags already are. A value holding
a ``%``, such as ``prompt = 50% done``, was ignored without any message, and ``%%`` or ``%(name)s`` were expanded.
