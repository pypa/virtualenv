import pytest
from testing.helpers import contains_exe

from virtualenv.create.via_global_ref.builtin.graalpy.graalpy import GraalPyPosix

GRAALPY_PATH = ("virtualenv.create.via_global_ref.builtin.graalpy.graalpy.Path",)


@pytest.mark.parametrize("py_info_name", ["linux_graalpy-managed22.3", "linux_graalpy22.3"])
def test_linux_graalpy22_3(py_info, mock_files):
    mock_files(GRAALPY_PATH, [py_info.system_executable])
    sources = tuple(GraalPyPosix.sources(interpreter=py_info))
    assert len(sources) == 2

    # Both graalpy-managed and graalpy will be "graalpy" symlink in the virtualenv
    assert contains_exe(sources, py_info.system_executable, "graalpy")

    # Check that extra tools are also added to the virtualenv
    for (source, targets) in py_info.extra_tools.items():
        assert contains_exe(sources, source, targets[0])
