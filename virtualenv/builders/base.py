class BaseBuilder(object):

    def __init__(self, python):
        self.python = python

    def create(self, destination):
        # Actually Create the virtual environment
        self.create_virtual_environment(destination)

    def create_virtual_environment(self, destination):
        raise NotImplementedError
