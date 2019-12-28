# -*- coding: utf-8 -*-
"""Activate virtualenv for current interpreter:

Use exec(open(this_file).read(), {'__file__': this_file}).

This can be used when you must use an existing Python interpreter, not the virtualenv bin/python.
"""
import json
import os
import site
import sys

try:
    __file__
except NameError:
    raise AssertionError("You must use exec(open(this_file).read(), {'__file__': this_file}))")

# prepend bin to PATH (this file is inside the bin directory)
bin_dir = os.path.dirname(os.path.abspath(__file__))
os.environ["PATH"] = os.pathsep.join([bin_dir] + os.environ.get("PATH", "").split(os.pathsep))

base = os.path.dirname(bin_dir)

# virtual env is right above bin directory
os.environ["VIRTUAL_ENV"] = base

# add the virtual environments site-packages to the host python import mechanism
prev = set(sys.path)

# fmt: off
# turn formatter off as json dumps will contain " characters - so we really need here ' black
site_packages = r'''
__SITE_PACKAGES__
'''

for site_package in json.loads(site_packages):
    if sys.version_info[0] == 2:
        site_package = site_package.encode('utf-8')
    path = os.path.realpath(os.path.join(os.path.dirname(__file__), site_package))
    site.addsitedir(path)
# fmt: on

sys.real_prefix = sys.prefix
sys.prefix = base

# Move the added items to the front of the path, in place
new = list(sys.path)
sys.path[:] = [i for i in new if i not in prev] + [i for i in new if i in prev]
