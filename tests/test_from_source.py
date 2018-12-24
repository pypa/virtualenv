"""test using the project from source/package rather than install"""
from __future__ import absolute_import, unicode_literals

import os
import subprocess
import sys

import pytest

import virtualenv

try:
    from pathlib import Path
except ImportError:
    from pathlib2 import Path

ROOT_DIR = Path(__file__).parents[1]


def test_use_from_source_tree(tmp_path, clean_python, monkeypatch):
    """test that we can create a virtual environment by feeding to a clean python the wheels content"""
    try:
        monkeypatch.chdir(tmp_path)
        subprocess.check_output(
            [
                str(Path(clean_python[1]) / virtualenv.EXPECTED_EXE),
                str(Path(ROOT_DIR) / "virtualenv.py"),
                "--no-download",
                "env",
            ],
            universal_newlines=True,
            stderr=subprocess.STDOUT,
        )
    except subprocess.CalledProcessError as exception:
        assert not exception.returncode, exception.output


@pytest.mark.skipif(os.environ.get("TOX_PACKAGE") is None, reason="needs tox provisioned sdist")
def test_use_from_source_sdist(tmp_path, clean_python, monkeypatch):
    """test that we can create a virtual environment by feeding to a clean python the sdist content"""
    monkeypatch.chdir(tmp_path)
    import tarfile

    tar = tarfile.open(os.environ.get("TOX_PACKAGE"), "r:gz")
    tar.extractall()

    virtualenv_file = next(tmp_path.iterdir()) / "virtualenv.py"
    assert virtualenv_file.exists()

    try:
        monkeypatch.chdir(tmp_path)
        subprocess.check_output(
            [str(Path(clean_python[1]) / virtualenv.EXPECTED_EXE), str(virtualenv_file), "--no-download", "env"],
            universal_newlines=True,
            stderr=subprocess.STDOUT,
        )
    except subprocess.CalledProcessError as exception:
        assert not exception.returncode, exception.output


def test_use_from_wheel(tmp_path, clean_python, monkeypatch):
    """test that we can create a virtual environment by feeding to a clean python the wheels content"""
    try:
        env = os.environ.copy()
        if virtualenv.IS_JYTHON:
            env[str("PIP_NO_CACHE_DIR")] = str("off")
        subprocess.check_output(
            [sys.executable, "-m", "pip", "wheel", "-w", str(tmp_path), "--no-deps", str(ROOT_DIR)],
            universal_newlines=True,
            stderr=subprocess.STDOUT,
            env=env,
        )
        wheels = list(tmp_path.glob("*.whl"))
        assert len(wheels) == 1
        wheel = wheels[0]
        import zipfile

        with zipfile.ZipFile(str(wheel), "r") as zip_ref:
            zip_ref.extractall(str(tmp_path / "out"))
        virtualenv_file = tmp_path / "out" / "virtualenv.py"
        try:
            monkeypatch.chdir(tmp_path)
            subprocess.check_output(
                [str(Path(clean_python[1]) / virtualenv.EXPECTED_EXE), str(virtualenv_file), "--no-download", "env"],
                universal_newlines=True,
                stderr=subprocess.STDOUT,
            )
        except subprocess.CalledProcessError as exception:
            assert not exception.returncode, exception.output
    except subprocess.CalledProcessError as exception:
        assert not exception.returncode, exception.output
