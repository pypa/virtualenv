"""
A simple shim module to fix up things on Python 2 only.

Note: until we setup correctly the paths we can only import built-ins.
"""
import sys


def main():
    """Patch what needed, and invoke the original site.py"""
    config = read_pyvenv()
    sys.real_prefix = sys.base_prefix = config["base-prefix"]
    sys.base_exec_prefix = config["base-exec-prefix"]
    sys.base_executable = config["base-executable"]
    global_site_package_enabled = config.get("include-system-site-packages", False) == "true"
    rewrite_standard_library_sys_path()
    disable_user_site_package()
    load_host_site()
    if global_site_package_enabled:
        add_global_site_package()


def load_host_site():
    """trigger reload of site.py - now it will use the standard library instance that will take care of init"""
    # we have a duality here, we generate the platform and pure library path based on what distutils.install specifies
    # because this is what pip will be using; the host site.py though may contain it's own pattern for where the
    # platform and pure library paths should exist

    # notably on Ubuntu there's a patch for getsitepackages to point to
    # - prefix + local/lib/pythonx.y/dist-packages
    # - prefix + lib/pythonx.y/dist-packages
    # while distutils.install.cmd still points both of these to
    # - prefix + lib/python2.7/site-packages

    # to facilitate when the two match, or not we first reload the site.py, now triggering the import of host site.py,
    # as this will ensure that initialization code within host site.py runs

    here = __file__  # the distutils.install patterns will be injected relative to this site.py, save it here

    with PatchForAppleFrameworkBuilds():
        reload(sys.modules["site"])  # noqa

    # and then if the distutils site packages are not on the sys.path we add them via add_site_dir; note we must add
    # them by invoking add_site_dir to trigger the processing of pth files
    import os

    site_packages = r"""
    ___EXPECTED_SITE_PACKAGES___
    """
    import json

    add_site_dir = sys.modules["site"].addsitedir
    for path in json.loads(site_packages):
        full_path = os.path.abspath(os.path.join(here, path.encode("utf-8")))
        if full_path not in sys.path:
            add_site_dir(full_path)


class PatchForAppleFrameworkBuilds(object):
    """Apple Framework builds unconditionally add the global site-package, escape this behaviour"""

    framework = None

    def __enter__(self):
        if sys.platform == "darwin":
            from sysconfig import get_config_var

            self.framework = get_config_var("PYTHONFRAMEWORK")
            if self.framework:
                sys.modules["sysconfig"]._CONFIG_VARS["PYTHONFRAMEWORK"] = None

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.framework:
            sys.modules["sysconfig"]._CONFIG_VARS["PYTHONFRAMEWORK"] = self.framework


def read_pyvenv():
    """read pyvenv.cfg"""
    os_sep = "\\" if sys.platform == "win32" else "/"  # no os module here yet - poor mans version
    config_file = "{}{}pyvenv.cfg".format(sys.prefix, os_sep)
    with open(config_file) as file_handler:
        lines = file_handler.readlines()
    config = {}
    for line in lines:
        try:
            split_at = line.index("=")
        except ValueError:
            continue  # ignore bad/empty lines
        else:
            config[line[:split_at].strip()] = line[split_at + 1 :].strip()
    return config


def rewrite_standard_library_sys_path():
    """Once this site file is loaded the standard library paths have already been set, fix them up"""
    sep = "\\" if sys.platform == "win32" else "/"
    exe_dir = sys.executable[: sys.executable.rfind(sep)]
    for at, value in enumerate(sys.path):
        # replace old sys prefix path starts with new
        if value == exe_dir:
            pass  # don't fix the current executable location, notably on Windows this gets added
        elif value.startswith(exe_dir):
            # content inside the exe folder needs to remap to original executables folder
            orig_exe_folder = sys.base_executable[: sys.base_executable.rfind(sep)]
            value = "{}{}".format(orig_exe_folder, value[len(exe_dir) :])
        elif value.startswith(sys.prefix):
            value = "{}{}".format(sys.base_prefix, value[len(sys.prefix) :])
        elif value.startswith(sys.exec_prefix):
            value = "{}{}".format(sys.base_exec_prefix, value[len(sys.exec_prefix) :])
        sys.path[at] = value


def disable_user_site_package():
    """Flip the switch on enable user site package"""
    # sys.flags is a c-extension type, so we cannot monkeypatch it, replace it with a python class to flip it
    sys.original_flags = sys.flags

    class Flags(object):
        def __init__(self):
            self.__dict__ = {key: getattr(sys.flags, key) for key in dir(sys.flags) if not key.startswith("_")}

    sys.flags = Flags()
    sys.flags.no_user_site = 1


def add_global_site_package():
    """add the global site package"""
    import site

    # add user site package
    sys.flags = sys.original_flags  # restore original
    site.ENABLE_USER_SITE = None  # reset user site check
    # add the global site package to the path - use new prefix and delegate to site.py
    orig_prefixes = None
    try:
        orig_prefixes = site.PREFIXES
        site.PREFIXES = [sys.base_prefix, sys.base_exec_prefix]
        site.main()
    finally:
        site.PREFIXES = orig_prefixes


main()
