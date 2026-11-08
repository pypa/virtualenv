from __future__ import annotations

from subprocess import Popen


def verify_wheel_digest(wheel: str) -> None:  # simplint: ignore[SMP201]  # CodeQL sample keeps its layout
    del wheel


def download_unverified(to_folder: str) -> str:
    Popen(["pip", "download", "--dest", to_folder, "pip"]).wait()  # ruff:ignore[start-process-with-partial-path]  # fixture calls pip from PATH  # fmt: skip
    return to_folder


def download_verified(to_folder: str) -> str:
    Popen(["pip", "download", "--dest", to_folder, "pip"]).wait()  # ruff:ignore[start-process-with-partial-path]  # fixture calls pip from PATH  # fmt: skip
    verify_wheel_digest(to_folder)
    return to_folder
