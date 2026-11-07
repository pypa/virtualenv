from __future__ import annotations

from subprocess import Popen


def download_unverified(to_folder: str) -> str:
    # the sample is the unverified download pattern CodeQL is meant to flag
    Popen(["pip", "download", "--dest", to_folder, "pip"]).wait()  # ruff:ignore[start-process-with-partial-path]
    return to_folder


def download_verified(to_folder: str) -> str:
    # the sample is the verified download pattern, kept as the contrast case
    Popen(["pip", "download", "--dest", to_folder, "pip"]).wait()  # ruff:ignore[start-process-with-partial-path]
    verify_wheel_digest(to_folder)
    return to_folder


def verify_wheel_digest(wheel: str) -> None:
    del wheel
