from __future__ import annotations

from typing import TYPE_CHECKING

from virtualenv.create.via_global_ref import api

if TYPE_CHECKING:
    from pytest_mock import MockerFixture


def test_can_symlink_when_symlinks_not_enabled(mocker: MockerFixture) -> None:
    mocker.patch.object(api, "fs_supports_symlink", return_value=False)
    assert api.ViaGlobalRefMeta().can_symlink is False
