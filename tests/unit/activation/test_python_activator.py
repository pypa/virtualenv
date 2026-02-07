from __future__ import annotations

import os
import sys
from argparse import Namespace
from ast import literal_eval
from textwrap import dedent

from virtualenv.activation import PythonActivator
from virtualenv.info import IS_WIN


def test_python_activator_generates_pkg_config_path(tmp_path):
    """Test that activate_this.py sets PKG_CONFIG_PATH."""

    class MockInterpreter:
        tcl_lib = None
        tk_lib = None

    class MockCreator:
        def __init__(self, dest):
            self.dest = dest
            self.bin_dir = dest / ("Scripts" if IS_WIN else "bin")
            self.bin_dir.mkdir(parents=True)
            self.libs = [dest / "Lib" / "site-packages"]
            self.env_name = "test-env"
            self.interpreter = MockInterpreter()
            self.pyenv_cfg = {}

    creator = MockCreator(tmp_path)
    options = Namespace(prompt=None)
    activator = PythonActivator(options)

    # Generate the activation script
    activator.generate(creator)

    # Read the generated script
    content = (creator.bin_dir / "activate_this.py").read_text(encoding="utf-8")

    # Verify PKG_CONFIG_PATH is set
    assert "PKG_CONFIG_PATH" in content
    assert "pkg_config_path" in content
    assert 'os.path.join(base, "lib", "pkgconfig")' in content


def test_python(raise_on_non_source_class, activation_tester):
    class Python(raise_on_non_source_class):
        def __init__(self, session) -> None:
            super().__init__(
                PythonActivator,
                session,
                sys.executable,
                activate_script="activate_this.py",
                extension="py",
                non_source_fail_message="You must use import runpy; runpy.run_path(this_file)",
            )
            self.unix_line_ending = not IS_WIN

        def env(self, tmp_path):
            env = os.environ.copy()
            env["PYTHONIOENCODING"] = "utf-8"
            for key in ("VIRTUAL_ENV", "PYTHONPATH"):
                env.pop(str(key), None)
            env["PATH"] = os.pathsep.join([str(tmp_path), str(tmp_path / "other")])
            return env

        @staticmethod
        def _get_test_lines(activate_script):
            raw = f"""
            import os
            import sys
            import platform
            import runpy

            def print_r(value):
                print(repr(value))

            print_r(os.environ.get("VIRTUAL_ENV"))
            print_r(os.environ.get("VIRTUAL_ENV_PROMPT"))
            print_r(os.environ.get("PATH").split(os.pathsep))
            print_r(sys.path)

            file_at = {str(activate_script)!r}
            # CPython 2 requires non-ascii path open to be unicode
            runpy.run_path(file_at)
            print_r(os.environ.get("VIRTUAL_ENV"))
            print_r(os.environ.get("VIRTUAL_ENV_PROMPT"))
            print_r(os.environ.get("PATH").split(os.pathsep))
            print_r(sys.path)

            import pydoc_test
            print_r(pydoc_test.__file__)
            """
            return dedent(raw).splitlines()

        def assert_output(self, out, raw, tmp_path):  # noqa: ARG002
            out = [literal_eval(i) for i in out]
            assert out[0] is None  # start with VIRTUAL_ENV None
            assert out[1] is None  # likewise for VIRTUAL_ENV_PROMPT

            prev_path = out[2]
            prev_sys_path = out[3]
            assert out[4] == str(self._creator.dest)  # VIRTUAL_ENV now points to the virtual env folder

            assert out[5] == str(self._creator.env_name)  # VIRTUAL_ENV_PROMPT now has the env name

            new_path = out[6]  # PATH now starts with bin path of current
            assert ([str(self._creator.bin_dir), *prev_path]) == new_path

            # sys path contains the site package at its start
            new_sys_path = out[7]

            new_lib_paths = {str(i) for i in self._creator.libs}
            assert prev_sys_path == new_sys_path[len(new_lib_paths) :]
            assert new_lib_paths == set(new_sys_path[: len(new_lib_paths)])

            # manage to import from activate site package
            dest = self.norm_path(self._creator.purelib / "pydoc_test.py")
            found = self.norm_path(out[8])
            assert found.startswith(dest)

        def non_source_activate(self, activate_script):
            act = str(activate_script)
            return [*self._invoke_script, "-c", f"exec(open({act!r}).read())"]

    activation_tester(Python)
