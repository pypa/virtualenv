"""Bootstrap."""

from __future__ import annotations

import logging
import re
import sys
from pathlib import Path
from subprocess import PIPE, CalledProcessError, Popen
from tempfile import TemporaryDirectory
from typing import TYPE_CHECKING, Final

from packaging.specifiers import InvalidSpecifier, Specifier
from packaging.utils import canonicalize_name

from .bundle import from_bundle
from .periodic_update import UnverifiedWheelError, add_wheel_to_update_log, verify_wheel_digest
from .util import Version, Wheel, discover_wheels

if TYPE_CHECKING:
    from virtualenv.app_data.base import AppData

LOGGER = logging.getLogger(__name__)

PIP_RUN: Final[str] = (
    "import sys; sys.path = [p for p in sys.path if p]; "
    "import runpy; runpy.run_module('pip', run_name='__main__', alter_sys=True)"
)

# A private index can legitimately serve a rebuilt wheel under the same distribution, version, and
# filename PyPI also uses - an internal mirror re-signing or re-packaging a release for policy reasons,
# for example. Verifying that file against PyPI's own digest would then reject a wheel that came from
# exactly the source it was configured to come from, not a compromised one. This does not attempt to
# find every way pip can be pointed elsewhere (a pip.conf file has the same effect and is invisible
# here), only the common, explicit one, so treat this as a conservative signal rather than proof either
# way: it exists to avoid false rejections, not to guarantee verification runs whenever it safely could.
_CUSTOM_INDEX_ENV_VARS: Final[tuple[str, ...]] = ("PIP_INDEX_URL", "PIP_EXTRA_INDEX_URL", "PIP_INDEX")


def _uses_default_index(env: dict[str, str]) -> bool:
    return not any(env.get(var) for var in _CUSTOM_INDEX_ENV_VARS)


# PEP 503 normalized distribution name. Anything outside this character set on the way to ``pip download`` means
# somebody is smuggling pip options or extras, so reject it before we build the command line.
_DISTRIBUTION_RE = re.compile(
    r"""
    ^
    (?P<name>
        [A-Za-z0-9]                 # must start with an alnum
        (?:[A-Za-z0-9._-]*           # inner chars: alnum plus . _ -
           [A-Za-z0-9])?             # must also end with an alnum (unless length is 1)
    )
    $
    """,
    re.VERBOSE,
)


def get_wheel(  # ruff:ignore[too-many-arguments]
    distribution: str,
    version: str | None,
    for_py_version: str,
    search_dirs: list[Path],
    download: bool,
    app_data: AppData,
    do_periodic_update: bool,
    env: dict[str, str],
) -> Wheel | None:
    """Get a wheel with the given distribution-version-for_py_version trio, by using the extra search dir + download."""
    # not all wheels are compatible with all python versions, so we need to py version qualify it
    wheel = None

    if not download or version != Version.bundle:
        # 1. acquire from bundle
        wheel = from_bundle(distribution, version, for_py_version, search_dirs, app_data, do_periodic_update, env)

    if download and wheel is None and version != Version.embed:
        # 2. download from the internet
        try:
            wheel = download_wheel(
                distribution=distribution,
                version_spec=Version.as_version_spec(version),
                for_py_version=for_py_version,
                search_dirs=search_dirs,
                app_data=app_data,
                to_folder=app_data.house,
                env=env,
            )
        except UnverifiedWheelError as exception:
            # only the bundle request has a local wheel that satisfies it; a pinned version must fail
            if version != Version.bundle:
                raise
            LOGGER.warning("%s, seeding the bundled %s instead", exception, distribution)
            return from_bundle(distribution, version, for_py_version, search_dirs, app_data, do_periodic_update, env)
        if wheel is not None and app_data.can_update:
            add_wheel_to_update_log(wheel, for_py_version, app_data)

    return wheel


def download_wheel(  # ruff:ignore[too-many-arguments]
    distribution: str,
    version_spec: str | None,
    for_py_version: str,
    search_dirs: list[Path],
    app_data: AppData,
    to_folder: Path,
    env: dict[str, str],
) -> Wheel:
    """Download one wheel into a private staging directory and move it into ``to_folder`` once it checks out.

    :raises ValueError: for an invalid distribution name or version specifier.
    :raises CalledProcessError: when ``pip download`` fails.
    :raises UnverifiedWheelError: when PyPI cannot supply the digest to verify against.
    :raises RuntimeError: when the staged file is not the requested wheel, its digest differs from PyPI's, or it does
        not support ``for_py_version``; nothing reaches ``to_folder`` in these cases.

    """
    _check_distribution(distribution)
    _check_version_spec(version_spec)
    to_download: Final = f"{distribution}{version_spec or ''}"
    if to_download.lower().endswith((
        ".zip",
        ".whl",
        ".tar",
        ".tar.gz",
        ".tgz",
        ".tar.bz2",
        ".tbz",
        ".tar.xz",
        ".txz",
        ".tlz",
        ".tar.lz",
        ".tar.lzma",
    )):
        msg = f"refusing to download wheel with archive-like requirement: {to_download!r}"
        raise ValueError(msg)
    LOGGER.debug("download wheel %s %s to %s", to_download, for_py_version, to_folder)
    verify_against_pypi: Final = _uses_default_index(env)
    env = pip_wheel_env_run(search_dirs, app_data, env)
    to_folder.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(dir=to_folder, prefix="download-") as staging:
        cmd: Final = [
            sys.executable,
            "-c",
            PIP_RUN,
            "download",
            "--progress-bar",
            "off",
            "--disable-pip-version-check",
            "--only-binary=:all:",
            "--no-deps",
            "--python-version",
            for_py_version,
            "-d",
            staging,
            to_download,
        ]
        process: Final = Popen(cmd, env=env, stdout=PIPE, stderr=PIPE, universal_newlines=True, encoding="utf-8")
        out, err = process.communicate()
        if process.returncode != 0:
            raise CalledProcessError(process.returncode, cmd, output=out, stderr=err)
        result: Final = _downloaded_wheel(Path(staging), distribution, version_spec)
        if verify_against_pypi:
            verify_wheel_digest(result)
        if not result.support_py(for_py_version):
            msg: Final = f"downloaded wheel {result.name} does not support Python {for_py_version}"
            raise RuntimeError(msg)
        destination: Final = to_folder / result.name
        result.path.replace(destination)
        return Wheel(destination)


def _downloaded_wheel(folder: Path, distribution: str, version_spec: str | None) -> Wheel:
    files: Final = list(folder.iterdir())
    if len(files) != 1 or files[0].is_symlink() or not files[0].is_file():
        msg: Final = f"could not find downloaded wheel for {distribution}: expected one archive"
        raise RuntimeError(msg)
    result: Final = Wheel.from_path(files[0])
    if (
        result is None
        or canonicalize_name(result.distribution) != canonicalize_name(distribution)
        or (version_spec and not Specifier(version_spec).contains(result.version))
    ):
        msg: Final = f"unexpected downloaded wheel {files[0].name} for {distribution}{version_spec or ''}"
        raise RuntimeError(msg)
    return result


def find_compatible_in_house(
    distribution: str, version_spec: str | None, for_py_version: str, in_folder: Path
) -> Wheel | None:
    wheels: Final[list[Wheel]] = discover_wheels(in_folder, distribution, None, for_py_version)
    if version_spec:
        specifier: Final[Specifier] = Specifier(version_spec)
        if specifier.operator not in {"==", "<"}:
            raise ValueError(version_spec)
        return next((wheel for wheel in wheels if specifier.contains(wheel.version)), None)
    return next(iter(wheels), None)


def pip_wheel_env_run(search_dirs: list[Path], app_data: AppData, env: dict[str, str]) -> dict[str, str]:
    env = env.copy()
    env.update({"PIP_USE_WHEEL": "1", "PIP_USER": "0", "PIP_NO_INPUT": "1", "PYTHONIOENCODING": "utf-8"})
    wheel = get_wheel(
        distribution="pip",
        version=None,
        for_py_version=f"{sys.version_info.major}.{sys.version_info.minor}",
        search_dirs=search_dirs,
        download=False,
        app_data=app_data,
        do_periodic_update=False,
        env=env,
    )
    if wheel is None:
        msg = "could not find the embedded pip"
        raise RuntimeError(msg)
    env["PYTHONPATH"] = str(wheel.path)
    return env


def _check_distribution(distribution: str) -> None:
    if not _DISTRIBUTION_RE.fullmatch(distribution):
        msg = f"refusing to download wheel for suspicious distribution name: {distribution!r}"
        raise ValueError(msg)


def _check_version_spec(version_spec: str | None) -> None:
    if not version_spec:
        return
    if not re.fullmatch(r"(?:==|<)[A-Za-z0-9._+!-]+", version_spec):
        msg = f"refusing to download wheel with suspicious version spec: {version_spec!r}"
        raise ValueError(msg)
    try:
        Specifier(version_spec)
    except InvalidSpecifier as exception:
        msg = f"refusing to download wheel with suspicious version spec: {version_spec!r}"
        raise ValueError(msg) from exception


__all__ = [
    "PIP_RUN",
    "download_wheel",
    "find_compatible_in_house",
    "get_wheel",
    "pip_wheel_env_run",
]
