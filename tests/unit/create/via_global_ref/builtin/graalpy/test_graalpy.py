from __future__ import annotations

import pytest

from virtualenv.create.via_global_ref.builtin.graalpy import GraalPy, GraalPyPosix, GraalPyWindows


@pytest.mark.parametrize("creator", [GraalPy, GraalPyPosix, GraalPyWindows])
def test_class_module(creator: type[GraalPy]) -> None:
    assert creator.__module__ == "virtualenv.create.via_global_ref.builtin.graalpy"
