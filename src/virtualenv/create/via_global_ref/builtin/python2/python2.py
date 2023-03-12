import abc
import json
import os
from pathlib import Path

from virtualenv.create.describe import Python2Supports
from virtualenv.create.via_global_ref.builtin.ref import PathRefToDest
from virtualenv.info import IS_ZIPAPP
from virtualenv.util.zipapp import read as read_from_zipapp

from ..via_global_self_do import ViaGlobalRefVirtualenvBuiltin

HERE = Path(os.path.abspath(__file__)).parent


class Python2(ViaGlobalRefVirtualenvBuiltin, Python2Supports, metaclass=abc.ABCMeta):
    def create(self):
        """Perform operations needed to make the created environment work on Python 2"""
        super().create()
        # install a patched site-package, the default Python 2 site.py is not smart enough to understand pyvenv.cfg,
        # so we inject a small shim that can do this, the location of this depends where it's on host
        sys_std_plat = Path(self.interpreter.system_stdlib_platform)
        site_py_in = (
            self.stdlib_platform
            if ((sys_std_plat / "site.py").exists() or (sys_std_plat / "site.pyc").exists())
            else self.stdlib
        )
        site_py = site_py_in / "site.py"

        custom_site = get_custom_site()
        if IS_ZIPAPP:
            custom_site_text = read_from_zipapp(custom_site)
        else:
            custom_site_text = custom_site.read_text(encoding="utf-8")
        expected = json.dumps([os.path.relpath(str(i), str(site_py)) for i in self.libs])

        custom_site_text = custom_site_text.replace("___EXPECTED_SITE_PACKAGES___", expected)

        reload_code = os.linesep.join(f"    {i}" for i in self.reload_code.splitlines()).lstrip()
        custom_site_text = custom_site_text.replace("# ___RELOAD_CODE___", reload_code)

        skip_rewrite = os.linesep.join(f"            {i}" for i in self.skip_rewrite.splitlines()).lstrip()
        custom_site_text = custom_site_text.replace("# ___SKIP_REWRITE____", skip_rewrite)

        site_py.write_text(custom_site_text, encoding="utf-8")

    @property
    def reload_code(self):
        return 'reload(sys.modules["site"])  # noqa # call system site.py to setup import libraries'

    @property
    def skip_rewrite(self):
        return ""

    @classmethod
    def sources(cls, interpreter):
        yield from super().sources(interpreter)
        # install files needed to run site.py, either from stdlib or stdlib_platform, at least pyc, but both if exists
        # if neither exists return the module file to trigger failure
        mappings, needs_py_module = (
            cls.mappings(interpreter),
            cls.needs_stdlib_py_module(),
        )
        for req in cls.modules():
            module_file, to_module, module_exists = cls.from_stdlib(mappings, f"{req}.py")
            compiled_file, to_compiled, compiled_exists = cls.from_stdlib(mappings, f"{req}.pyc")
            if needs_py_module or module_exists or not compiled_exists:
                yield PathRefToDest(module_file, dest=to_module)
            if compiled_exists:
                yield PathRefToDest(compiled_file, dest=to_compiled)

    @staticmethod
    def from_stdlib(mappings, name):
        for from_std, to_std in mappings:
            src = from_std / name
            if src.exists():
                return src, to_std, True
        # if not exists, fallback to first in list
        return mappings[0][0] / name, mappings[0][1], False

    @classmethod
    def mappings(cls, interpreter):
        mappings = [(Path(interpreter.system_stdlib_platform), cls.to_stdlib_platform)]
        if interpreter.system_stdlib_platform != interpreter.system_stdlib:
            mappings.append((Path(interpreter.system_stdlib), cls.to_stdlib))
        return mappings

    def to_stdlib(self, src):
        return self.stdlib / src.name

    def to_stdlib_platform(self, src):
        return self.stdlib_platform / src.name

    @classmethod
    def needs_stdlib_py_module(cls):
        raise NotImplementedError

    @classmethod
    def modules(cls):
        return []


def get_custom_site():
    return HERE / "site.py"
