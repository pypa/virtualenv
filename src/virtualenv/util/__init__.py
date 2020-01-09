from __future__ import absolute_import, unicode_literals

import sys

if sys.verison_info[0] == 3:
    import configparser as ConfigParser
else:
    import ConfigParser


__all__ = ("ConfigParser",)
