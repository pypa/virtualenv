import errno
import os
import os.path

import pretend
import pytest

from virtualenv._utils import copyfile, ensure_directory


class TestCopyfile:

    def test_copy(self, tmpdir):
        src = str(tmpdir.join("src.txt"))
        dst = str(tmpdir.join("dst.txt"))

        with open(src, "wb") as fp:
            fp.write(b"some text")

        copyfile(src, dst)

        assert os.path.exists(dst)

        with open(dst, "rb") as fp:
            assert fp.read() == b"some text"

    def test_copy_executable(self, tmpdir):
        src = str(tmpdir.join("src.exe"))
        dst = str(tmpdir.join("dst.exe"))

        with open(src, "wb") as fp:
            fp.write(b"an executable")
        os.chmod(src, 0o0700)

        copyfile(src, dst)

        assert os.path.exists(dst)
        assert os.access(dst, os.X_OK)


class TestEnsureDirectory:

    def test_passes_args_and_kwargs(self, monkeypatch):
        fake_makedirs = pretend.call_recorder(lambda *a, **kw: None)
        monkeypatch.setattr(os, "makedirs", fake_makedirs)
        ensure_directory("lolwat", 1, 2, three=3, four=4)
        assert fake_makedirs.calls == [
            pretend.call("lolwat", 1, 2, three=3, four=4),
        ]

    def test_oserror_raises(self, monkeypatch):
        @pretend.call_recorder
        def fake_makedirs(*args, **kwargs):
            raise OSError(errno.EROFS, "A Fake Error")

        monkeypatch.setattr(os, "makedirs", fake_makedirs)

        with pytest.raises(OSError) as exc:
            ensure_directory("lolwat")

        assert exc.value.errno == errno.EROFS

    def test_directory_which_doesnt_exist(self, tmpdir):
        target_dir = str(tmpdir.join("somedir"))
        assert not os.path.exists(target_dir)
        ensure_directory(target_dir)
        assert os.path.exists(target_dir)

    def test_directory_which_exists(self, tmpdir):
        target_dir = str(tmpdir.join("somedir"))
        os.makedirs(target_dir)
        assert os.path.exists(target_dir)
        ensure_directory(target_dir)
        assert os.path.exists(target_dir)
