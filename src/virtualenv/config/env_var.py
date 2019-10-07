from __future__ import absolute_import, unicode_literals

import os

from .convert import convert


def get_env_var(key, as_type):
    """Get the environment variable option.

    :param key: the config key requested
    :param as_type: the type we would like to convert it to
    :return:
    """
    environ_key = "VIRTUALENV_{}".format(key.upper())
    if environ_key in os.environ:
        value = os.environ[environ_key]
        # noinspection PyBroadException
        try:
            source = "env var {}".format(environ_key)
            as_type = convert(value, as_type, source)
            return as_type, source
        except Exception:
            pass


__all__ = ("get_env_var",)
