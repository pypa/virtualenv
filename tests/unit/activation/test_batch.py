from __future__ import annotations

from argparse import Namespace

import pytest

from virtualenv.activation import BatchActivator


@pytest.mark.parametrize(
    ("tcl_lib", "tk_lib", "present"),
    [
        ("C:\\tcl", "C:\\tk", True),
        (None, None, False),
    ],
)
def test_batch_tkinter_generation(tmp_path, tcl_lib, tk_lib, present):
    # GIVEN
    class MockInterpreter:
        os = "nt"

    interpreter = MockInterpreter()
    interpreter.tcl_lib = tcl_lib
    interpreter.tk_lib = tk_lib

    class MockCreator:
        def __init__(self, dest):
            self.dest = dest
            self.bin_dir = dest / "bin"
            self.bin_dir.mkdir()
            self.interpreter = interpreter
            self.pyenv_cfg = {}
            self.env_name = "my-env"

    creator = MockCreator(tmp_path)
    options = Namespace(prompt=None)
    activator = BatchActivator(options)

    # WHEN
    activator.generate(creator)
    activate_content = (creator.bin_dir / "activate.bat").read_text(encoding="utf-8")
    deactivate_content = (creator.bin_dir / "deactivate.bat").read_text(encoding="utf-8")

    # THEN
    if present:
        assert '@if NOT "C:\\tcl"=="" @set "TCL_LIBRARY=C:\\tcl"' in activate_content
        assert '@if NOT "C:\\tk"=="" @set "TK_LIBRARY=C:\\tk"' in activate_content
        assert "if defined _OLD_VIRTUAL_TCL_LIBRARY" in deactivate_content
        assert "if defined _OLD_VIRTUAL_TK_LIBRARY" in deactivate_content
    else:
        assert '@if NOT ""=="" @set "TCL_LIBRARY="' in activate_content
        assert '@if NOT ""=="" @set "TK_LIBRARY="' in activate_content


@pytest.mark.usefixtures("activation_python")
def test_batch(activation_tester_class, activation_tester, tmp_path):
    version_script = tmp_path / "version.bat"
    version_script.write_text("ver", encoding="utf-8")

    class Batch(activation_tester_class):
        def __init__(self, session) -> None:
            super().__init__(BatchActivator, session, None, "activate.bat", "bat")
            self._version_cmd = [str(version_script)]
            self._invoke_script = []
            self.deactivate = "call deactivate"
            self.activate_cmd = "call"
            self.pydoc_call = f"call {self.pydoc_call}"
            self.unix_line_ending = False

        def _get_test_lines(self, activate_script):
            return ["@echo off", *super()._get_test_lines(activate_script)]

        def quote(self, s):
            if '"' in s or " " in s:
                text = s.replace('"', r"\"")
                return f'"{text}"'
            return s

        def print_prompt(self):
            return 'echo "%PROMPT%"'

    activation_tester(Batch)


@pytest.mark.usefixtures("activation_python")
def test_batch_output(activation_tester_class, activation_tester, tmp_path):
    version_script = tmp_path / "version.bat"
    version_script.write_text("ver", encoding="utf-8")

    class Batch(activation_tester_class):
        def __init__(self, session) -> None:
            super().__init__(BatchActivator, session, None, "activate.bat", "bat")
            self._version_cmd = [str(version_script)]
            self._invoke_script = []
            self.deactivate = "call deactivate"
            self.activate_cmd = "call"
            self.pydoc_call = f"call {self.pydoc_call}"
            self.unix_line_ending = False

        def _get_test_lines(self, activate_script):
            """
            Build intermediary script which will be then called.
            In the script just activate environment, call echo to get current
            echo setting, and then deactivate. This ensures that echo setting
            is preserved and no unwanted output appears.
            """
            intermediary_script_path = str(tmp_path / "intermediary.bat")
            activate_script_quoted = self.quote(str(activate_script))
            return [
                "@echo on",
                f"@echo @call {activate_script_quoted} > {intermediary_script_path}",
                f"@echo @echo >> {intermediary_script_path}",
                f"@echo @deactivate >> {intermediary_script_path}",
                f"@call {intermediary_script_path}",
            ]

        def assert_output(self, out, raw, tmp_path):  # noqa: ARG002
            assert out[0] == "ECHO is on.", raw

        def quote(self, s):
            if '"' in s or " " in s:
                text = s.replace('"', r"\"")
                return f'"{text}"'
            return s

        def print_prompt(self):
            return 'echo "%PROMPT%"'

    activation_tester(Batch)
