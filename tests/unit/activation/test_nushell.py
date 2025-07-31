from __future__ import annotations

from shutil import which

from virtualenv.activation import NushellActivator
from virtualenv.info import IS_WIN


def test_nushell(activation_tester_class, activation_tester):
    class Nushell(activation_tester_class):
        def __init__(self, session) -> None:
            cmd = which("nu")
            if cmd is None and IS_WIN:
                cmd = "c:\\program files\\nu\\bin\\nu.exe"

            super().__init__(NushellActivator, session, cmd, "activate.nu", "nu")

            self.activate_cmd = "overlay use"
            self.deactivate = "overlay hide activate"
            self.unix_line_ending = not IS_WIN

        def print_prompt(self):
            return r"print $env.VIRTUAL_PREFIX"

        def activate_call(self, script):
            # Commands are called without quotes in Nushell
            cmd = self.activate_cmd
            scr = self.quote(str(script))
            return f"{cmd} {scr}".strip()

        def _get_test_lines(self, activate_script):
            lines = super()._get_test_lines(activate_script)
            lines.insert(3, self.print_os_env_var("PKG_CONFIG_PATH"))
            i = next(i for i, line in enumerate(lines) if "pydoc" in line)
            lines.insert(i, self.print_os_env_var("PKG_CONFIG_PATH"))
            lines.insert(-1, self.print_os_env_var("PKG_CONFIG_PATH"))
            return lines

        def assert_output(self, out, raw, tmp_path):
            assert out[3] == "None"

            pkg_config_path = self.norm_path(self._creator.dest / "lib" / "pkgconfig")
            assert self.norm_path(out[9]) == pkg_config_path

            assert out[-2] == "None"
            super().assert_output(out[:3] + out[4:9] + out[10:-2] + [out[-1]], raw, tmp_path)

    activation_tester(Nushell)
