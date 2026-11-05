Name the option, the value and the available choices when ``VIRTUALENV_CREATOR``, ``VIRTUALENV_SEEDER`` or
``virtualenv.ini`` sets a creator or seeder that is not available, as ``VIRTUALENV_DISCOVERY`` already does. The error
used to be ``No implementation for PythonInfo(...)``, which blamed the interpreter.
