from __future__ import absolute_import, unicode_literals

import os
import sys
from ast import literal_eval
from textwrap import dedent

from virtualenv.activation import PythonActivator
from virtualenv.info import IS_WIN, WIN_CPYTHON_2
from virtualenv.util.six import ensure_text


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
            self.unix_line_ending = not IS_WIN

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
            import platform

            def print_r(value):
                print(repr(value))

            print_r(os.environ.get("VIRTUAL_ENV"))
            print_r(os.environ.get("PATH").split(os.pathsep))
            print_r(sys.path)

            file_at = {!r}
            # CPython 2 requires non-ascii path open to be unicode
            with open(file_at{}, "r") as file_handler:
                content = file_handler.read()
            exec(content, {{"__file__": file_at}})

            print_r(os.environ.get("VIRTUAL_ENV"))
            print_r(os.environ.get("PATH").split(os.pathsep))
            print_r(sys.path)

            import pydoc_test
            print_r(pydoc_test.__file__)
            """.format(
                str(activate_script),
                ".decode('utf-8')" if WIN_CPYTHON_2 else "",
            )
            result = dedent(raw).splitlines()
            return result

        def assert_output(self, out, raw, tmp_path):
            out = [literal_eval(i) for i in out]
            assert out[0] is None  # start with VIRTUAL_ENV None

            prev_path = out[1]
            prev_sys_path = out[2]
            assert out[3] == str(self._creator.dest)  # VIRTUAL_ENV now points to the virtual env folder

            new_path = out[4]  # PATH now starts with bin path of current
            assert ([str(self._creator.bin_dir)] + prev_path) == new_path

            # sys path contains the site package at its start
            new_sys_path = out[5]

            new_lib_paths = {ensure_text(j) if WIN_CPYTHON_2 else j for j in {str(i) for i in self._creator.libs}}
            assert prev_sys_path == new_sys_path[len(new_lib_paths) :]
            assert new_lib_paths == set(new_sys_path[: len(new_lib_paths)])

            # manage to import from activate site package
            dest = self.norm_path(self._creator.purelib / "pydoc_test.py")
            found = self.norm_path(out[6].decode(sys.getfilesystemencoding()) if WIN_CPYTHON_2 else out[6])
            assert found.startswith(dest)

        def non_source_activate(self, activate_script):
            act = str(activate_script)
            if WIN_CPYTHON_2:
                act = ensure_text(act)
            cmd = self._invoke_script + [
                "-c",
                "exec(open({}).read())".format(repr(act)),
            ]
            return cmd

    activation_tester(Python)
