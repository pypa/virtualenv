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
    global_site_package_enabled = config.get("include-system-site-packages", False) == "true"
    rewrite_standard_library_sys_path()
    disable_user_site_package()
    load_host_site()
    if global_site_package_enabled:
        add_global_site_package()


def load_host_site():
    """trigger reload of site.py - now it will use the standard library instance that will take care of init"""
    # the standard library will be the first element starting with the real prefix, not zip, must be present
    import os

    std_lib = os.path.dirname(os.__file__)
    std_lib_suffix = std_lib[len(sys.real_prefix) :]  # strip away the real prefix to keep just the suffix

    reload(sys.modules["site"])  # noqa

    # ensure standard library suffix/site-packages is on the new path
    # notably Debian derivatives change site-packages constant to dist-packages, so will not get added
    target = os.path.join("{}{}".format(sys.prefix, std_lib_suffix), "site-packages")
    if target not in reversed(sys.path):  # if wasn't automatically added do it explicitly
        sys.path.append(target)


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
        elif value.startswith(sys.prefix):
            value = "{}{}".format(sys.base_prefix, value[len(sys.prefix) :])
        elif value.startswith(sys.exec_prefix):
            value = "{}{}".format(sys.base_exec_prefix, value[len(sys.exec_prefix) :])
        sys.path[at] = value


def disable_user_site_package():
    """Flip the switch on enable user site package"""
    # sys.flags is a c-extension type, so we cannot monkey patch it, replace it with a python class to flip it
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
