# -*- coding: utf-8 -*-
"""
Distutils allows user to configure some arguments via a configuration file:
https://docs.python.org/3/install/index.html#distutils-configuration-files

Some of this arguments though don't make sense in context of the virtual environment files, let's fix them up.
"""
import os
import sys

VIRTUALENV_PATCH_FILE = os.path.join(__file__)


def patch(dist_of):
    # we cannot allow the prefix override as that would get packages installed outside of the virtual environment
    old_parse_config_files = dist_of.Distribution.parse_config_files

    def parse_config_files(self, *args, **kwargs):
        result = old_parse_config_files(self, *args, **kwargs)
        install_dict = self.get_option_dict("install")

        if "prefix" in install_dict:  # the prefix governs where to install the libraries
            install_dict["prefix"] = VIRTUALENV_PATCH_FILE, os.path.abspath(sys.prefix)

        if "install_scripts" in install_dict:  # the install_scripts governs where to generate console scripts
            script_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "__SCRIPT_DIR__"))
            install_dict["install_scripts"] = VIRTUALENV_PATCH_FILE, script_path

        return result

    dist_of.Distribution.parse_config_files = parse_config_files


def run():
    # patch distutils
    from distutils import dist

    patch(dist)

    # patch setuptools (that has it's own copy of the dist package)
    try:
        from setuptools import dist
    except ImportError:
        pass  # if setuptools is not around that's alright, just don't patch
    else:
        patch(dist)


run()
