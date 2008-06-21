import os
import sys
import warnings 
import ConfigParser # ConfigParser is not a virtualenv module, so we can use it to find the stdlib

dirname = os.path.dirname

distutils_path = os.path.join(os.path.dirname(ConfigParser.__file__), 'distutils')
if os.path.normpath(distutils_path) == os.path.dirname(os.path.normpath(__file__)):
    warnings.warn(
        "The virtualenv distutils package at %s appears to be in the same location as the system distutils?")
else:
    __path__.insert(0, distutils_path)
    exec open(os.path.join(distutils_path, '__init__.py')).read()

import dist
import sysconfig

## distutils.dist patches:

old_find_config_files = dist.Distribution.find_config_files
def find_config_files(self):
    found = old_find_config_files(self)
    system_distutils = os.path.join(distutils_path, 'distutils.cfg')
    if os.path.exists(system_distutils):
        found.insert(0, system_distutils)
    return found
dist.Distribution.find_config_files = find_config_files

## distutils.sysconfig patches:

old_get_python_inc = sysconfig.get_python_inc
def sysconfig_get_python_inc(plat_specific=0, prefix=None):
    if prefix is None:
        prefix = sys.real_prefix
    return old_get_python_inc(plat_specific, prefix)
sysconfig_get_python_inc.__doc__ = old_get_python_inc.__doc__
sysconfig.get_python_inc = sysconfig_get_python_inc

old_get_python_lib = sysconfig.get_python_lib
def sysconfig_get_python_lib(plat_specific=0, standard_lib=0, prefix=None):
    if standard_lib and prefix is None:
        prefix = sys.real_prefix
    return old_get_python_lib(plat_specific, standard_lib, prefix)
sysconfig_get_python_lib.__doc__ = old_get_python_lib.__doc__
sysconfig.get_python_lib = sysconfig_get_python_lib

##FIXME: Should I patch sysconfig.get_config_vars ?
##       It has a lot of stuff, most of which doesn't seem to be used.
