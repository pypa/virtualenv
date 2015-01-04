from __future__ import absolute_import, division, print_function

try:
    FileNotFoundError = FileNotFoundError
except NameError:  # pragma: no cover
    FileNotFoundError = OSError
