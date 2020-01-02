from __future__ import absolute_import, unicode_literals

try:
    import ConfigParser
except ImportError:
    # noinspection PyPep8Naming
    import configparser as ConfigParser


__all__ = ("ConfigParser",)
