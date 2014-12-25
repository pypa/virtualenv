import glob
import os.path
import subprocess
import sys


WHEEL_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "_bundled",
)


class BaseBuilder(object):

    def __init__(self, python, system_site_packages=False, clear=False,
                 pip=True, setuptools=True):
        # We default to sys.executable if we're not given a Python.
        if python is None:
            python = sys.executable

        self.python = python
        self.system_site_packages = system_site_packages
        self.clear = clear
        self.pip = pip
        self.setuptools = setuptools

    def create(self, destination):
        # Actually Create the virtual environment
        self.create_virtual_environment(destination)

        # Install our activate scripts into the virtual environment
        self.install_scripts(destination)

        # Install the packaging tools (pip and setuptools) into the virtual
        # environment.
        self.install_tools(destination)

    def create_virtual_environment(self, destination):
        raise NotImplementedError

    def install_scripts(self, destination):
        pass

    def install_tools(self, destination):
        # Determine which projects we are going to install
        projects = []
        if self.pip:
            projects.append("pip")
        if self.setuptools:
            projects.append("setuptools")

        # Short circuit if we're not going to install anything
        if not projects:
            return

        # Compute the path to the Python interpreter inside the virtual
        # environment.
        python = os.path.join(destination, "bin", "python")

        # Find all of the Wheels inside of our WHEEL_DIR
        wheels = glob.iglob(os.path.join(WHEEL_DIR, "*.whl"))

        # We want to add the pip wheel to the virtual environment's PYTHONPATH
        # and then import it and manually run the install routines to install
        # the projects that we want to install.
        command = [
            python, "-m", "pip", "install", "--no-index", "--isolated",
            "--find-links", WHEEL_DIR,
        ]
        subprocess.check_call(
            command + projects,
            env={
                "PYTHONPATH": os.pathsep.join(wheels),
            },
        )
