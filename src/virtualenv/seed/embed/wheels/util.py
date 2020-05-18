from zipfile import ZipFile

from virtualenv.util.six import ensure_text


class Wheel(object):
    def __init__(self, path):
        # https://www.python.org/dev/peps/pep-0427/#file-name-convention
        # The wheel filename is {distribution}-{version}(-{build tag})?-{python tag}-{abi tag}-{platform tag}.whl
        self.path = path
        self._parts = path.stem.split("-")

    @classmethod
    def from_path(cls, path):
        if path.suffix == ".whl" and len(path.stem.split("-")) >= 5:
            return cls(path)
        return None

    @property
    def distribution(self):
        return self._parts[0]

    @property
    def version(self):
        return self._parts[1]

    @property
    def version_tuple(self):
        result = []
        for part in self.version.split(".")[0:3]:
            try:
                result.append(int(part))
            except ValueError:
                break
        return tuple(result)

    @property
    def name(self):
        return self.path.name

    def support_py(self, py_version):
        name = "{}.dist-info/METADATA".format("-".join(self.path.stem.split("-")[0:2]))
        with ZipFile(ensure_text(str(self.path)), "r") as zip_file:
            metadata = zip_file.read(name).decode("utf-8")
        marker = "Requires-Python:"
        requires = next((i[len(marker) :] for i in metadata.splitlines() if i.startswith(marker)), None)
        if requires is None:  # if it does not specify a python requires the assumption is compatible
            return True
        py_version_int = tuple(int(i) for i in py_version.split("."))
        for require in (i.strip() for i in requires.split(",")):
            # https://www.python.org/dev/peps/pep-0345/#version-specifiers
            for operator, check in [
                ("!=", lambda v: py_version_int != v),
                ("==", lambda v: py_version_int == v),
                ("<=", lambda v: py_version_int <= v),
                (">=", lambda v: py_version_int >= v),
                ("<", lambda v: py_version_int < v),
                (">", lambda v: py_version_int > v),
            ]:
                if require.startswith(operator):
                    ver_str = require[len(operator) :].strip()
                    version = tuple((int(i) if i != "*" else None) for i in ver_str.split("."))[0:2]
                    if not check(version):
                        return False
                    break
        return True

    def __repr__(self):
        return "{}({})".format(self.__class__.__name__, self.path)

    def __str__(self):
        return str(self.path)
