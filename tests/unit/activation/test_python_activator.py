from __future__ import absolute_import, unicode_literals

import os
import sys
from textwrap import dedent

import pytest
import six

from virtualenv.activation import PythonActivator
from virtualenv.info import IS_PYPY, IS_WIN


@pytest.mark.xfail(
    condition=IS_PYPY and six.PY2 and IS_WIN and bool(os.environ.get(str("CI_RUN"))),
    strict=False,
    reason="this fails in the CI only, nor sure how, if anyone can reproduce help",
)
def test_python(raise_on_non_source_class, activation_tester):
    class Python(raise_on_non_source_class):
        def __init__(self, session):
            super(Python, self).__init__(
                PythonActivator,
                session,
                sys.executable,
                activate_script="activate_this.py",
                extension="py",
                non_source_fail_message="You must use exec(open(this_file).read(), {'__file__': this_file}))",
            )

        def env(self, tmp_path):
            env = os.environ.copy()
            env[str("PYTHONIOENCODING")] = str("utf-8")
            for key in {"VIRTUAL_ENV", "PYTHONPATH"}:
                env.pop(str(key), None)
            env[str("PATH")] = os.pathsep.join([str(tmp_path), str(tmp_path / "other")])
            return env

        @staticmethod
        def _get_test_lines(activate_script):
            raw = """
            import os
            import sys

            def print_path(value):
                if value is not None and (
                    sys.version_info[0] == 2 and isinstance(value, str) and not hasattr(sys, "pypy_version_info")
                ):
                    value = value.decode(sys.getfilesystemencoding())
                print(value)

            print_path(os.environ.get("VIRTUAL_ENV"))
            print_path(os.environ.get("PATH"))
            print_path(os.pathsep.join(sys.path))
            file_at = {}
            with open(file_at, "rb") as file_handler:
                content = file_handler.read()
            exec(content, {{"__file__": file_at}})
            print_path(os.environ.get("VIRTUAL_ENV"))
            print_path(os.environ.get("PATH"))
            print_path(os.pathsep.join(sys.path))
            import inspect
            import pydoc_test

            print_path(inspect.getsourcefile(pydoc_test))
            """.format(
                repr(six.ensure_text(str(activate_script)))
            )
            result = dedent(raw).splitlines()
            return result

        def assert_output(self, out, raw, tmp_path):
            assert out[0] == "None"  # start with VIRTUAL_ENV None

            prev_path = out[1].split(os.path.pathsep)
            prev_sys_path = out[2].split(os.path.pathsep)

            assert out[3] == six.ensure_text(
                str(self._creator.dest)
            )  # VIRTUAL_ENV now points to the virtual env folder

            new_path = out[4].split(os.pathsep)  # PATH now starts with bin path of current
            assert ([six.ensure_text(str(self._creator.bin_dir))] + prev_path) == new_path

            # sys path contains the site package at its start
            new_sys_path = out[5].split(os.path.pathsep)

            new_lib_paths = {six.ensure_text(str(i)) for i in self._creator.libs}
            assert prev_sys_path == new_sys_path[len(new_lib_paths) :]
            assert new_lib_paths == set(new_sys_path[: len(new_lib_paths)])

            # manage to import from activate site package
            assert self.norm_path(out[6]) == self.norm_path(self._creator.purelib / "pydoc_test.py")

        def non_source_activate(self, activate_script):
            return self._invoke_script + [
                "-c",
                'exec(open(r"{}").read())'.format(six.ensure_text(str(activate_script))),
            ]

    activation_tester(Python)
