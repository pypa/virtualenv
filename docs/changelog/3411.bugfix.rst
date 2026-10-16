Keep unset-variable bookkeeping out of exported xonsh variables, so child shells do not restore an internal sentinel as
``PYTHONHOME``. Skip xonsh activation for destination names that its PATH handling would expand to a different path.
