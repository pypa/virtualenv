import os
import sys
from collections import OrderedDict
from pathlib import Path

from ..via_template import ViaTemplateActivator


class PythonActivator(ViaTemplateActivator):
    def templates(self):
        yield Path("activate_this.py")

    def replacements(self, creator, dest_folder):
        replacements = super().replacements(creator, dest_folder)
        lib_folders = OrderedDict((os.path.relpath(str(i), str(dest_folder)), None) for i in creator.libs)
        win_py2 = creator.interpreter.platform == "win32" and creator.interpreter.version_info.major == 2
        replacements.update(
            {
                "__LIB_FOLDERS__": os.pathsep.join(lib_folders.keys()),
                "__DECODE_PATH__": ("yes" if win_py2 else ""),
            },
        )
        return replacements

    @staticmethod
    def _repr_unicode(creator, value):
        py2 = creator.interpreter.version_info.major == 2
        if py2:  # on Python 2 we need to encode this into explicit utf-8, py3 supports unicode literals
            start = 2 if sys.version_info[0] == 3 else 1
            value = repr(value.encode("utf-8"))[start:-1]
        return value


__all__ = [
    "PythonActivator",
]
