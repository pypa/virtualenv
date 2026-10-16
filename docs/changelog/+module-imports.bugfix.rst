Remove Python's implicit working-directory import entry before handling ``python -m virtualenv`` commands, reducing
accidental module shadowing during environment creation. Explicit import paths keep their existing order.
