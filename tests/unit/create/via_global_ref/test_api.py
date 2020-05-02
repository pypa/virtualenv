from virtualenv.create.via_global_ref import api


def test_can_symlink_when_symlinks_not_enabled(mocker):
    mocker.patch.object(api, "fs_supports_symlink", return_value=False)
    assert api.ViaGlobalRefMeta().can_symlink is False
