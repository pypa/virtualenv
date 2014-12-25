import json
import os.path
import subprocess

from virtualenv.builders.base import BaseBuilder
from virtualenv._utils import copyfile, ensure_directory


SITECUSTOMIZE = """
import sys

# Create an empty sys_path which we'll build up to create our final sys.path
sys_path = []

# Check to see if "" is the first item the sys.path, if it is then re-add it
# to our new sys.path
if sys.path[:1] == [""]:
    sys_path.append("")

# Hack the sys.path so that it matches the sys.path of the *real* Python, sans
# any site-packages.
sys_path.extend(__SYS_PATH__)

# Add on the site-packages directory of the virtual environment to the very end
# of the sys.path
sys_path.append("__SITE_PACKAGES__")

# Replace the running sys.path with our newly created one.
sys.path = sys_path

# Now that we've fixed up our sys.path, let's purge everything out of
# sys.modules except for sys.modules itself. This will mean that from here on
# out any imports will be pulling from the global interpreter instead of the
# virtual environment, other than site-packages.
for key in list(sys.modules):
    # We don't want to purge these modules because if we do, then things break
    # very badly.
    if key in ["sys", "site", "sitecustomize", "__builtin__", "__main__"]:
        continue

    del sys.modules[key]
"""


class LegacyBuilder(BaseBuilder):

    @classmethod
    def check_available(self, python):
        # TODO: Do we ever want to make this builder *not* available?
        return True

    def _get_sys_version_info(self):
        # We want to get the sys.version_info of the target Python. Since that
        # may not be the currently executing Python we'll go ahead and create
        # a subprocess and use it to inspect the target environment's
        # sys.version_info.
        return tuple(
            json.loads(
                subprocess.check_output([
                    self.python, "-c",
                    "import sys,json; "
                    "print(json.dumps(tuple(sys.version_info)))",
                ]).decode("utf8"),
            ),
        )

    def _get_sys_executable(self):
        # We want to get the sys.executable of the target Python. Since that
        # may not be the currently executing Python we'll go ahead and create
        # a subprocess and use it to inspect the target environment's
        # sys.executable.
        return json.loads(
            subprocess.check_output([
                self.python, "-c",
                "import sys,json; print(json.dumps(sys.executable))",
            ]).decode("utf8"),
        )

    def _get_lib_directory(self):
        return json.loads(
            subprocess.check_output([
                self.python, "-c",
                "import os,os.path,json; "
                "print(json.dumps(os.path.dirname(os.__file__)))",
            ]).decode("utf8"),
        )

    def _get_sys_path(self):
        # TODO: Ensure that the -S flag will also prevent processing .pth
        # from inside the site-packages.
        return [
            x for x in json.loads(
                subprocess.check_output([
                    self.python, "-S", "-c",
                    "import sys,json; "
                    "print(json.dumps(sys.path))",
                ]).decode("utf8"),
            )
            if x
        ]

    def create_virtual_environment(self, destination):
        # Get the Python version of the target Python
        python_verison = self._get_sys_version_info()

        # Resolve the Python interpreter to the real actual file
        python = os.path.realpath(self._get_sys_executable())

        # Create our binaries that we'll use to create the virtual environment
        bin_dir = os.path.join(destination, "bin")
        ensure_directory(bin_dir)
        for i in range(3):
            copyfile(
                python,
                os.path.join(
                    bin_dir,
                    "python{}".format(".".join(map(str, python_verison[:i]))),
                ),
            )

        # Create our lib directory, this is going to hold all of the parts of
        # the standard library that we need in order to ensure that we can
        # successfully bootstrap a Python interpreter.
        lib_dir = os.path.join(
            destination,
            "lib",
            "python{}".format(".".join(map(str, python_verison[:2]))),
        )
        ensure_directory(lib_dir)

        # Create our site-packages directory, this is the thing that end users
        # really want control over.
        site_packages_dir = os.path.join(lib_dir, "site-packages")
        ensure_directory(site_packages_dir)

        # Determine the stdlib directory for the target Python
        target_lib_dir = self._get_lib_directory()

        # The Python interpreter uses the os.py module as a sort of sentinel
        # value for where it can locate the rest of it's files. It will first
        # look relative to the bin directory, so we can copy the os.py file
        # from the target Python into our lib directory to trick Python into
        # using our virtual environment's prefix as it's own.
        # Note: At this point we'll have a broken environment, because it will
        # only have the os module but none of the os's modules dependencies or
        # any other module unless they are "special" modules built into the
        # interpreter like the sys module.
        copyfile(
            os.path.join(target_lib_dir, "os.py"),
            os.path.join(lib_dir, "os.py"),
        )

        # Next we need to copy over the site module, this is because now that
        # the Python interpreter is rooted in our new location, one of the
        # first things it's going to do is attempt to import the site module
        # so we'll want to make that available for it.
        copyfile(
            os.path.join(target_lib_dir, "site.py"),
            os.path.join(lib_dir, "site.py"),
        )

        # The site module has a number of required modules that it needs in
        # order to be successfully imported, so we'll copy each of those module
        # into our virtual environment's lib directory as well. Note that this
        # list also includes the os module, but since we've already copied
        # that we'll go ahead and omit it.
        modules = {
            "posixpath.py", "stat.py", "genericpath.py", "warnings.py",
            "linecache.py", "types.py", "UserDict.py", "_abcoll.py", "abc.py",
            "copy_reg.py", "_weakrefset.py", "traceback.py", "sysconfig.py",
            "re.py", "sre_compile.py", "sre_parse.py", "sre_constants.py",
            "_sysconfigdata.py", "_osx_support.py",
        }
        for module in modules:
            copyfile(
                os.path.join(target_lib_dir, module),
                os.path.join(lib_dir, module),
            )

        # Now we're going to install our own sitecustomize.py file. This file
        # is how we're going to adjust things like sys.path and such so that
        # they reflect the values that we want them to inside of the virtual
        # environment.
        dst = os.path.join(lib_dir, "sitecustomize.py")
        with open(dst, "w", encoding="utf8") as dst_fp:
            # Get the data from our source file, and replace our special
            # variables with the computed data.
            data = SITECUSTOMIZE
            data = data.replace("__SYS_PATH__", repr(self._get_sys_path()))
            data = data.replace("__SITE_PACKAGES__", site_packages_dir)

            # Write the final sitecustomize.py file to our lib directory
            dst_fp.write(data)
