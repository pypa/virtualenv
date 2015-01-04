import io
import json
import os.path
import subprocess
import textwrap

from virtualenv.builders.base import BaseBuilder
from virtualenv._utils import copyfile, ensure_directory


SITE = """# -*- encoding: utf-8 -*-
import sys
import os.path

# We want to stash the global site-packages here, this will be None if we're
# not adding them.
global_site_packages = __GLOBAL_SITE_PACKAGES__

# We want to make sure that our sys.prefix and sys.exec_prefix match the
# locations in our virtual enviornment.
sys.prefix = __PREFIX__
sys.exec_prefix = __EXEC_PREFIX__

# We want to record what the "real/base" prefix is of the virtual environment.
sys.base_prefix = __BASE_PREFIX__
sys.base_exec_prefix = __BASE_EXEC_PREFIX__

# At the point this code is running, the only paths on the sys.path are the
# paths that the interpreter adds itself. These are essentially the locations
# it looks for the various stdlib modules. Since we are inside of a virtual
# environment these will all be relative to the sys.prefix and sys.exec_prefix,
# however we want to change these to be relative to sys.base_prefix and
# sys.base_exec_prefix instead.
new_sys_path = []
for path in sys.path:
    # TODO: Is there a better way to determine this?
    if path.startswith(sys.prefix):
        path = os.path.join(
            sys.base_prefix,
            path[len(sys.prefix) + 1:],
        )
    elif path.startswith(sys.exec_prefix):
        path = os.path.join(
            sys.base_exec_prefix,
            path[len(sys.exec_prefix) + 1:],
        )

    new_sys_path.append(path)
sys.path = new_sys_path

# We want to empty everything that has already been imported from the
# sys.modules so that any additional imports of these modules will import them
# from the base Python and not from the copies inside of the virtual
# environment. This will ensure that our copies will only be used for
# bootstrapping the virtual environment.
for key in list(sys.modules):
    # We don't want to purge these modules because if we do, then things break
    # very badly.
    if key in ["sys", "site", "sitecustomize", "__builtin__", "__main__"]:
        continue

    del sys.modules[key]

# We want to trick the interpreter into thinking that the user specific
# site-packages has been requested to be disabled. We'll do this by mimicing
# that sys.flags.no_user_site has been set to False, however sys.flags is a
# read-only structure so we'll temporarily replace it with one that has the
# same values except for sys.flags.no_user_site which will be set to True.
_real_sys_flags = sys.flags
class AttrDict(dict):
    def __init__(self, *args, **kwargs):
        dict.__init__(self, *args, **kwargs)
    def __getattr__(self, name):
        return self[name]
sys.flags = AttrDict((k, getattr(sys.flags, k)) for k in dir(sys.flags))
sys.flags["no_user_site"] = True

# We want to import the *real* site module from the base Python. Actually
# attempting to do an import here will just import this module again, so we'll
# just read the real site module and exec it.
with open(__SITE__) as fp:
    exec(fp.read())

# Restore the real sys.flags
sys.flags = _real_sys_flags

# If we're running with the global site-packages enabled, then we'll want to
# go ahead and enable it here so that it comes after the virtual environment's
# site-package.
if global_site_packages is not None:
    # Force a re-check of ENABLE_USER_SITE so that we get the "real" value
    # instead of our forced off value.
    ENABLE_USER_SITE = check_enableusersite()

    # Add the actual user site-packages if we're supposed to.
    addusersitepackages(None)

    # Add the actual global site-packages.
    for path in global_site_packages:
        addsitedir(path)
"""


class LegacyBuilder(BaseBuilder):

    @classmethod
    def check_available(self, python):
        # TODO: Do we ever want to make this builder *not* available?
        return True

    def _get_base_python_info(self):
        # Get information from the base python that we need in order to create
        # a legacy virtual environment.
        return json.loads(
            subprocess.check_output([
                self.python,
                "-c",
                textwrap.dedent("""
                import json
                import os
                import os.path
                import site
                import sys

                def resolve(path):
                    return os.path.realpath(os.path.abspath(path))

                print(
                    json.dumps({
                        "sys.version_info": tuple(sys.version_info),
                        "sys.executable": resolve(sys.executable),
                        "sys.prefix": resolve(sys.prefix),
                        "sys.exec_prefix": resolve(sys.exec_prefix),
                        "site.getsitepackages": [
                            resolve(f) for f in site.getsitepackages()
                        ],
                        "lib": resolve(os.path.dirname(os.__file__)),
                        "site.py": os.path.join(
                            resolve(os.path.dirname(site.__file__)),
                            "site.py",
                        ),
                    })
                )
                """),
            ]).decode("utf8"),
        )

    def create_virtual_environment(self, destination):
        # Get a bunch of information from the base Python.
        base_python = self._get_base_python_info()

        # Create our binaries that we'll use to create the virtual environment
        bin_dir = os.path.join(destination, self.flavor.bin_dir)
        ensure_directory(bin_dir)
        for python_bin in self.flavor.python_bins(
                base_python["sys.version_info"]):
            copyfile(
                base_python["sys.executable"],
                os.path.join(bin_dir, python_bin),
            )

        # Create our lib directory, this is going to hold all of the parts of
        # the standard library that we need in order to ensure that we can
        # successfully bootstrap a Python interpreter.
        lib_dir = os.path.join(
            destination,
            self.flavor.lib_dir(base_python["sys.version_info"])
        )
        ensure_directory(lib_dir)

        # Create our site-packages directory, this is the thing that end users
        # really want control over.
        site_packages_dir = os.path.join(lib_dir, "site-packages")
        ensure_directory(site_packages_dir)

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
            os.path.join(base_python["lib"], "os.py"),
            os.path.join(lib_dir, "os.py"),
        )

        # The site module has a number of required modules that it needs in
        # order to be successfully imported, so we'll copy each of those module
        # into our virtual environment's lib directory as well. Note that this
        # list also includes the os module, but since we've already copied
        # that we'll go ahead and omit it.

        for module in self.flavor.core_modules:
            copyfile(
                os.path.join(base_python["lib"], module),
                os.path.join(lib_dir, module),
            )

        dst = os.path.join(lib_dir, "site.py")
        with io.open(dst, "wb") as dst_fp:
            # Get the data from our source file, and replace our special
            # variables with the computed data.
            data = SITE
            data = data.replace("__PREFIX__", repr(destination))
            data = data.replace("__EXEC_PREFIX__", repr(destination))
            data = data.replace(
                "__BASE_PREFIX__",
                repr(base_python["sys.prefix"]),
            )
            data = data.replace(
                "__BASE_EXEC_PREFIX__", repr(base_python["sys.exec_prefix"]),
            )
            data = data.replace("__SITE__", repr(base_python["site.py"]))
            data = data.replace(
                "__GLOBAL_SITE_PACKAGES__",
                repr(
                    base_python["site.getsitepackages"]
                    if self.system_site_packages else None
                ),
            )

            # Write the final site.py file to our lib directory
            dst_fp.write(data)
