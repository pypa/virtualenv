Keep a version specifier such as ``>=3.9,<3.10`` as one value when it is given through ``VIRTUALENV_PYTHON`` or the
config file on a single line. It was split at the comma, so the upper bound was dropped and a newer interpreter could be
picked.
