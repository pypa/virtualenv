from __future__ import absolute_import, unicode_literals

import inspect
import os
import sys

import six

from virtualenv.activation import PythonActivator


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
            for key in {"VIRTUAL_ENV", "PYTHONPATH"}:
                env.pop(str(key), None)
            env[str("PATH")] = os.pathsep.join([str(tmp_path), str(tmp_path / "other")])
            return env

        def _get_test_lines(self, activate_script):
            raw = inspect.getsource(self.activate_this_test)
            return ["# -*- coding: utf-8 -*-"] + [
                i[12:] for i in raw.replace("__FILENAME__", six.ensure_text(str(activate_script))).splitlines()[2:]
            ]

        # noinspection PyUnresolvedReferences
        @staticmethod
        def activate_this_test():
            import os
            import sys

            print(os.environ.get("VIRTUAL_ENV"))
            print(os.environ.get("PATH"))
            print(os.pathsep.join(sys.path))
            file_at = r"__FILENAME__"
            with open(file_at, "rt") as file_handler:
                content = file_handler.read()
            exec(content, {"__file__": file_at})
            print(os.environ.get("VIRTUAL_ENV"))
            print(os.environ.get("PATH"))
            print(os.pathsep.join(sys.path))
            import inspect
            import pydoc_test

            print(inspect.getsourcefile(pydoc_test))

        def assert_output(self, out, raw, tmp_path):
            assert out[0] == "None"  # start with VIRTUAL_ENV None

            prev_path = out[1].split(os.path.pathsep)
            prev_sys_path = out[2].split(os.path.pathsep)

            assert out[3] == six.ensure_text(
                str(self._creator.dest_dir)
            )  # VIRTUAL_ENV now points to the virtual env folder

            new_path = out[4].split(os.pathsep)  # PATH now starts with bin path of current
            assert ([six.ensure_text(str(self._creator.bin_dir))] + prev_path) == new_path

            # sys path contains the site package at its start
            new_sys_path = out[5].split(os.path.pathsep)
            assert ([six.ensure_text(str(i)) for i in self._creator.site_packages] + prev_sys_path) == new_sys_path

            # manage to import from activate site package
            assert self.norm_path(out[6]) == self.norm_path(self._creator.site_packages[0] / "pydoc_test.py")

        def non_source_activate(self, activate_script):
            return self._invoke_script + [
                "-c",
                'exec(open(r"{}").read())'.format(six.ensure_text(str(activate_script))),
            ]

    activation_tester(Python)
