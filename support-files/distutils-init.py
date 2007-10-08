import os
import warnings # warnings is not a virtualenv module, so we can use it to find the stdlib

dirname = os.path.dirname

distutils_path = os.path.join(os.path.dirname(warnings.__file__), 'distutils')
__path__.insert(0, distutils_path)
exec open(os.path.join(distutils_path, '__init__.py')).read()

import dist

old_find_config_files = dist.Distribution.find_config_files
def find_config_files(self):
    found = old_find_config_files(self)
    system_distutils = os.path.join(distutils_path, 'distutils.cfg')
    if os.path.exists(system_distutils):
        found.insert(0, system_distutils)
    return found
dist.Distribution.find_config_files = find_config_files

