"""Read which release files the package index pip is configured with marks as yanked."""

from __future__ import annotations

import configparser
import json
import locale
import logging
import netrc
import os
import ssl
import sys
from base64 import b64encode
from html.parser import HTMLParser
from http.client import HTTPException
from pathlib import Path
from typing import TYPE_CHECKING, Final
from urllib.parse import unquote, urlsplit, urlunsplit
from urllib.request import HTTPSHandler, ProxyHandler, Request, build_opener

from packaging.utils import canonicalize_name
from platformdirs import site_config_dir, site_data_dir, user_config_dir, user_data_dir

if TYPE_CHECKING:
    from collections.abc import Mapping
    from urllib.request import BaseHandler

_LOGGER: Final[logging.Logger] = logging.getLogger(__name__)


def yanked_files(distribution: str, env: Mapping[str, str]) -> frozenset[str] | None:
    """Ask the package indexes pip would use which files of a distribution are yanked (PEP 592).

    pip is not run: its index, extra index, certificate and proxy settings are read from the same configuration files
    and ``PIP_*`` environment variables it reads, and each index answers one simple API request (PEP 691 JSON or PEP 503
    HTML).

    :param distribution: the distribution name, for example ``pip``
    :param env: the environment variables pip would run with

    :returns: the yanked file names, a file listed on several indexes only when every one of them yanked it; ``None``
        when an index could not be read or pip is configured not to use one

    """
    try:
        settings: Final = _pip_settings(env)
    # platformdirs raises RuntimeError when no home folder is known, so the per-user configuration cannot be found
    except (configparser.Error, UnicodeDecodeError, RuntimeError) as exception:
        _LOGGER.warning("could not read the pip configuration to check for yanked releases: %r", exception)
        return None
    if settings.get("no-index", "").lower() in {"y", "yes", "t", "true", "on", "1"}:
        return None
    flags: Final[dict[str, list[bool]]] = {}
    for index_url in [
        settings.get("index-url", "https://pypi.org/simple/"),
        *settings.get("extra-index-url", "").split(),
    ]:
        if (files := _read_project_page(index_url, distribution, settings, env)) is None:
            return None
        for filename, yanked in files.items():
            flags.setdefault(filename, []).append(yanked)
    return frozenset(filename for filename, yanked in flags.items() if all(yanked))


def _pip_settings(env: Mapping[str, str]) -> dict[str, str]:
    # mirrors pip's precedence: later configuration files win, [download] wins over [global], PIP_* wins over both
    parser: Final = _PipConfigParser()
    if env.get("PIP_CONFIG_FILE") != os.devnull:
        # pip reads its configuration files in the locale encoding unless Python runs in UTF-8 mode
        parser.read(_pip_config_files(env), encoding="utf-8" if sys.flags.utf8_mode else _locale_encoding())
    settings: Final = {
        key: value
        for section in ("global", "download")
        if parser.has_section(section)
        for key, value in parser.items(section)
        if value
    }
    settings.update({
        key[4:].lower().replace("_", "-"): value for key, value in env.items() if key.startswith("PIP_") and value
    })
    return settings


class _PipConfigParser(configparser.RawConfigParser):
    def optionxform(self, optionstr: str) -> str:
        return optionstr.lower().replace("_", "-")


def _pip_config_files(env: Mapping[str, str]) -> list[Path]:
    name: Final = "pip.ini" if sys.platform == "win32" else "pip.conf"
    if sys.platform == "darwin":
        site_folders = site_data_dir("pip", appauthor=False, multipath=True).split(os.pathsep)
    elif sys.platform == "win32":
        site_folders = [site_config_dir("pip", appauthor=False)]
    else:
        site_folders = [*site_config_dir("pip", appauthor=False, multipath=True).split(os.pathsep), "/etc"]
    files: Final = [Path(folder, name) for folder in site_folders]
    env_file: Final = env.get("PIP_CONFIG_FILE")
    # pip skips the per-user files when PIP_CONFIG_FILE names an existing file
    # os.path answers False where Path raises on a folder it may not enter, before Python 3.14
    if not (env_file and os.path.exists(env_file)):
        user_folder = Path(user_config_dir("pip", appauthor=False, roaming=True))
        if sys.platform == "darwin":
            mac_folder = user_data_dir("pip", appauthor=False, roaming=True)
            user_folder = Path(mac_folder if os.path.isdir(mac_folder) else os.path.expanduser("~/.config/pip"))
        # os.path leaves ~ as is when no home folder is known, where Path.expanduser raises
        legacy_folder = os.path.expanduser(os.path.join("~", "pip" if sys.platform == "win32" else ".pip"))
        files.extend((Path(legacy_folder, name), user_folder / name))
    files.append(Path(sys.prefix, name))
    if env_file:
        files.append(Path(env_file))
    return files


def _locale_encoding() -> str:
    if sys.version_info >= (3, 11):
        return locale.getencoding()
    return locale.getpreferredencoding(do_setlocale=False)


def _read_project_page(
    index_url: str, distribution: str, settings: Mapping[str, str], env: Mapping[str, str]
) -> dict[str, bool] | None:
    # the raw index URL may carry a password, so the log names it only once the credentials are stripped
    page_url = "an index URL that does not parse"
    try:
        split = urlsplit(index_url)
        page_url = urlunsplit((
            split.scheme,
            split.netloc.rpartition("@")[2],
            f"{split.path.rstrip('/')}/{canonicalize_name(distribution)}/",
            "",
            "",
        ))
        if split.scheme == "file":
            page_url += "index.html"
        files: Final = _parse_project_page(*_fetch(page_url, split.username, split.password, settings, env))
    # a page nested deeply enough to exhaust the JSON parser's recursion is as unreadable as a malformed one
    except (OSError, ValueError, HTTPException, RecursionError) as exception:
        _LOGGER.warning("could not read %s to check for yanked releases: %r", page_url, exception)
        return None
    return files


def _parse_project_page(content_type: str, body: str) -> dict[str, bool]:
    if content_type != "application/vnd.pypi.simple.v1+json":
        anchors: Final = _AnchorParser()
        try:
            anchors.feed(body)
        except AssertionError as exception:
            # html.parser raised AssertionError on some malformed markup until its 2025 hardening, as in 3.12.0
            msg = f"the project page has markup the parser rejects: {exception}"
            raise ValueError(msg) from exception
        return anchors.files
    document: Final = json.loads(body)
    files: Final = document.get("files") if isinstance(document, dict) else None
    if not isinstance(files, list):
        msg = "the project page has no files list"
        # a malformed page is a ValueError so it is reported like an unparsable one
        raise ValueError(msg)  # ruff:ignore[type-check-without-type-error]
    result: Final[dict[str, bool]] = {}
    for entry in files:
        if isinstance(entry, dict) and isinstance(filename := entry.get("filename"), str):
            # PEP 691 marks a yanked file with true or with the reason as a string
            _add_listing(result, filename, yanked=bool(entry.get("yanked")))
    return result


class _AnchorParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.files: dict[str, bool] = {}

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes: Final = dict(attrs)
        if tag == "a" and (href := attributes.get("href")):
            # PEP 592 marks a yanked file with the data-yanked attribute, its value is the optional reason
            _add_listing(
                self.files, unquote(urlsplit(href).path.rpartition("/")[2]), yanked="data-yanked" in attributes
            )


def _add_listing(files: dict[str, bool], filename: str, *, yanked: bool) -> None:
    # a file listed more than once counts as yanked only when every listing says so
    files[filename] = files.get(filename, True) and yanked


def _fetch(
    page_url: str, username: str | None, password: str | None, settings: Mapping[str, str], env: Mapping[str, str]
) -> tuple[str, str]:
    # the URL is the index pip is configured with, and a file:// mirror is a valid one
    request: Final = Request(  # ruff:ignore[suspicious-url-open-usage]
        page_url, headers={"Accept": "application/vnd.pypi.simple.v1+json, text/html;q=0.1"}
    )
    if (credentials := _credentials(username, password, urlsplit(page_url).hostname, env)) is not None:
        request.add_unredirected_header("Authorization", f"Basic {b64encode(credentials.encode()).decode()}")
    limit: Final = 16 * 1024 * 1024
    # the timeout bounds each socket operation, not the whole request
    with build_opener(*_handlers(settings)).open(request, timeout=15) as response:
        body = response.read(limit + 1)
        # a chunked response has no length to check, http.client ignores Content-Length then
        chunked = response.headers.get("Transfer-Encoding", "").lower() == "chunked"
        declared = "" if chunked else response.headers.get("Content-Length", "")
        content_type = response.headers.get_content_type()
        charset = response.headers.get_content_charset() or "utf-8"
    if len(body) > limit:
        msg = f"the project page is larger than {limit} bytes"
        raise ValueError(msg)
    # a short read returns what arrived, so a page cut off mid-transfer would look like a shorter listing
    if declared.isdecimal() and len(body) < int(declared):
        msg = f"the project page ended after {len(body)} of {declared} bytes"
        raise ValueError(msg)
    try:
        text = body.decode(charset, errors="replace")
    # an unknown charset, or a codec that is not a text encoding such as base64
    except LookupError:
        text = body.decode("utf-8", errors="replace")
    return content_type, text


def _credentials(
    username: str | None, password: str | None, hostname: str | None, env: Mapping[str, str]
) -> str | None:
    # like pip: a user and password in the URL win, then .netrc, then the URL's user without a password
    if username is not None and password is not None:
        return f"{unquote(username)}:{unquote(password)}"
    if (from_netrc := _netrc_credentials(hostname, env)) is not None:
        return from_netrc
    return None if username is None else f"{unquote(username)}:"


def _netrc_credentials(hostname: str | None, env: Mapping[str, str]) -> str | None:
    # follows requests, which pip uses: NETRC names the file, otherwise the first of ~/.netrc and ~/_netrc that exists
    candidates: Final = [env["NETRC"]] if "NETRC" in env else ["~/.netrc", "~/_netrc"]
    path: Final = next((path for path in map(os.path.expanduser, candidates) if os.path.exists(path)), None)
    if hostname is None or path is None:
        return None
    try:
        # an explicit path skips the ownership and permission checks netrc applies to its default file
        entry = netrc.netrc(path).authenticators(hostname)
    except (netrc.NetrcParseError, OSError):
        return None
    if entry is None or not any(entry):
        return None
    return f"{entry[0] or entry[1] or ''}:{entry[2] or ''}"


def _handlers(settings: Mapping[str, str]) -> list[BaseHandler]:
    handlers: Final[list[BaseHandler]] = []
    if proxy := settings.get("proxy"):
        handlers.append(ProxyHandler({"http": proxy, "https": proxy}))
    if cert := settings.get("cert"):
        handlers.append(HTTPSHandler(context=ssl.create_default_context(cafile=cert)))
    return handlers


__all__ = [
    "yanked_files",
]
