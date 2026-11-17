Run the ``pip`` seeder with the embedded ``pip`` that supports the Python version of the environment, not the one of the
Python running virtualenv. Seeding a Python 3.9 environment with ``--seeder pip`` from Python 3.10 or later failed, as
the newer ``pip`` does not run on Python 3.9.
