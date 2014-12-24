import sys


class BaseBuilder(object):

    def __init__(self, python, system_site_packages=False, clear=False):
        # We default to sys.executable if we're not given a Python.
        if python is None:
            python = sys.executable

        self.python = python
        self.system_site_packages = system_site_packages
        self.clear = clear

    def create(self, destination):
        # Actually Create the virtual environment
        self.create_virtual_environment(destination)

    def create_virtual_environment(self, destination):
        raise NotImplementedError
