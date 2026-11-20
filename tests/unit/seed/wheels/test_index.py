from __future__ import annotations

import json
import os
import sys
from base64 import b64encode
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
from typing import TYPE_CHECKING, Final, NamedTuple, NoReturn
from urllib.error import URLError

import pytest

from virtualenv.seed.wheels.index import yanked_files

if TYPE_CHECKING:
    from collections.abc import Generator
    from pathlib import Path

    from pytest_mock import MockerFixture, MockType

_JSON: Final[str] = "application/vnd.pypi.simple.v1+json"


@pytest.fixture
def server() -> Generator[_Server, None, None]:
    yield from _serve()


def _serve() -> Generator[_Server, None, None]:
    running: Final[_Server] = _Server()
    Thread(target=running.httpd.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True).start()
    yield running
    running.httpd.shutdown()
    running.httpd.server_close()


class _Server:
    def __init__(self) -> None:
        self.pages: dict[str, _Page] = {}
        self.auth: str | None = None
        self.received_auth: list[str | None] = []
        owner: Final[_Server] = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:
                owner.received_auth.append(self.headers.get("Authorization"))
                if owner.auth is not None and self.headers.get("Authorization") != owner.auth:
                    self.send_error(401)
                    return
                status, headers, body = owner.pages.get(self.path, _Page(404, {}, b""))
                self.send_response(status)
                for name, value in headers.items():
                    self.send_header(name, value)
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *_: object) -> None: ...

        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.httpd.server_address[1]}"


@pytest.fixture
def other_server() -> Generator[_Server, None, None]:
    yield from _serve()


class _Page(NamedTuple):
    status: int
    headers: dict[str, str]
    body: bytes


def _page(body: str, content_type: str = "text/html") -> _Page:
    return _Page(200, {"Content-Type": content_type}, body.encode())


def test_yanked_files_reads_a_file_index(tmp_path: Path) -> None:
    index: Final[str] = _file_index(tmp_path, {"pip-1.0-py3-none-any.whl": None, "pip-2.0-py3-none-any.whl": ""})

    result: Final[frozenset[str] | None] = yanked_files("pip", {"PIP_INDEX_URL": index, "PIP_CONFIG_FILE": os.devnull})

    assert result == {"pip-2.0-py3-none-any.whl"}


def _file_index(tmp_path: Path, files: dict[str, str | None]) -> str:
    project: Final[Path] = tmp_path / "simple" / "pip"
    project.mkdir(parents=True)
    (project / "index.html").write_text(_html(files), encoding="utf-8")
    return (tmp_path / "simple").as_uri()


def _html(files: dict[str, str | None]) -> str:
    return "<h1>Links for pip</h1>\n" + "".join(
        f'<a href="../../files/{name}#sha256=00"{"" if yank is None else f" data-yanked={yank!r}"}>{name}</a>\n'
        for name, yank in files.items()
    )


@pytest.mark.parametrize(
    ("yanked", "expected"),
    [
        pytest.param(True, {"pip-2.0-py3-none-any.whl"}, id="flag"),
        pytest.param("broken metadata", {"pip-2.0-py3-none-any.whl"}, id="reason"),
        pytest.param(False, set(), id="not-yanked"),
    ],
)
def test_yanked_files_reads_pep_691_json(server: _Server, yanked: bool | str, expected: set[str]) -> None:
    files: Final[list[dict[str, str | bool] | str]] = [
        {"filename": "pip-2.0-py3-none-any.whl", "yanked": yanked},
        {"url": "no-filename"},
        "not-a-file",
    ]
    server.pages["/simple/pip/"] = _page(json.dumps({"files": files}), _JSON)

    result: Final[frozenset[str] | None] = yanked_files(
        "pip", {"PIP_INDEX_URL": f"{server.url}/simple", "PIP_CONFIG_FILE": os.devnull}
    )

    assert result == expected


def test_yanked_files_sends_credentials_from_the_index_url(server: _Server) -> None:
    server.auth = f"Basic {b64encode(b'user:p@ss').decode()}"
    server.pages["/simple/pip/"] = _page(_html({"pip-2.0-py3-none-any.whl": "bad"}))
    index: Final[str] = f"http://user:p%40ss@{server.url.removeprefix('http://')}/simple/"

    result: Final[frozenset[str] | None] = yanked_files("pip", {"PIP_INDEX_URL": index, "PIP_CONFIG_FILE": os.devnull})

    assert result == {"pip-2.0-py3-none-any.whl"}


@pytest.mark.parametrize(
    ("name", "variable"),
    [
        pytest.param(".netrc", "UNRELATED", id="home-netrc"),
        pytest.param("_netrc", "UNRELATED", id="home-underscore-netrc"),
        pytest.param("credentials", "NETRC", id="netrc-variable"),
    ],
)
def test_yanked_files_sends_credentials_from_netrc(
    server: _Server, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, name: str, variable: str
) -> None:
    netrc_file: Final[Path] = tmp_path / name
    netrc_file.write_text("machine 127.0.0.1 login user password secret\n", encoding="utf-8")
    # world readable, which the default netrc lookup would reject
    netrc_file.chmod(0o644)
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    server.auth = f"Basic {b64encode(b'user:secret').decode()}"
    server.pages["/simple/pip/"] = _page(_html({"pip-2.0-py3-none-any.whl": "bad"}))
    env: Final[dict[str, str]] = {"PIP_INDEX_URL": f"{server.url}/simple/", "PIP_CONFIG_FILE": os.devnull}

    result: Final[frozenset[str] | None] = yanked_files("pip", {**env, variable: str(netrc_file)})

    assert result == {"pip-2.0-py3-none-any.whl"}


@pytest.mark.parametrize(
    "content",
    [
        pytest.param("machine elsewhere.example login user password secret\n", id="other-host"),
        pytest.param("machine\n", id="malformed"),
    ],
)
def test_yanked_files_netrc_without_credentials_still_reads_the_index(
    server: _Server, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, content: str
) -> None:
    (tmp_path / ".netrc").write_text(content, encoding="utf-8")
    (tmp_path / ".netrc").chmod(0o644)
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    server.pages["/simple/pip/"] = _page(_html({"pip-2.0-py3-none-any.whl": "bad"}))

    result: Final[frozenset[str] | None] = yanked_files(
        "pip", {"PIP_INDEX_URL": f"{server.url}/simple/", "PIP_CONFIG_FILE": os.devnull}
    )

    assert result == {"pip-2.0-py3-none-any.whl"}
    assert server.received_auth == [None]


def test_yanked_files_keeps_credentials_from_a_redirect(server: _Server, other_server: _Server) -> None:
    server.auth = f"Basic {b64encode(b'user:secret').decode()}"
    server.pages["/simple/pip/"] = _Page(302, {"Location": f"{other_server.url}/simple/pip/"}, b"")
    other_server.pages["/simple/pip/"] = _page(_html({"pip-2.0-py3-none-any.whl": ""}))
    index: Final[str] = f"http://user:secret@{server.url.removeprefix('http://')}/simple/"

    result: Final[frozenset[str] | None] = yanked_files("pip", {"PIP_INDEX_URL": index, "PIP_CONFIG_FILE": os.devnull})

    assert result == {"pip-2.0-py3-none-any.whl"}
    assert other_server.received_auth == [None]


def test_yanked_files_never_logs_the_password(server: _Server, caplog: pytest.LogCaptureFixture) -> None:
    server.pages["/simple/pip/"] = _Page(500, {}, b"")
    index: Final[str] = f"http://user:s3cret@{server.url.removeprefix('http://')}/simple/"

    assert yanked_files("pip", {"PIP_INDEX_URL": index, "PIP_CONFIG_FILE": os.devnull}) is None
    assert "could not read" in caplog.text
    assert "s3cret" not in caplog.text


@pytest.mark.parametrize(
    ("extra", "expected"),
    [
        pytest.param(None, set(), id="listed-on-other-index"),
        pytest.param("", {"pip-2.0-py3-none-any.whl"}, id="yanked-on-every-index"),
    ],
)
def test_yanked_files_needs_every_index_to_yank(server: _Server, extra: str | None, expected: set[str]) -> None:
    server.pages["/a/pip/"] = _page(_html({"pip-2.0-py3-none-any.whl": ""}))
    server.pages["/b/pip/"] = _page(_html({"pip-2.0-py3-none-any.whl": extra}))
    env: Final[dict[str, str]] = {
        "PIP_INDEX_URL": f"{server.url}/a/",
        "PIP_EXTRA_INDEX_URL": f"{server.url}/b/",
        "PIP_CONFIG_FILE": os.devnull,
    }

    assert yanked_files("pip", env) == expected


def test_yanked_files_goes_through_the_configured_proxy(server: _Server) -> None:
    server.pages["http://index.invalid/simple/pip/"] = _page(_html({"pip-2.0-py3-none-any.whl": ""}))
    env: Final[dict[str, str]] = {
        "PIP_INDEX_URL": "http://index.invalid/simple/",
        "PIP_PROXY": server.url,
        "PIP_CONFIG_FILE": os.devnull,
    }

    assert yanked_files("pip", env) == {"pip-2.0-py3-none-any.whl"}


@pytest.mark.parametrize(
    ("env", "expected"),
    [
        pytest.param({}, "https://pypi.org/simple/pip/", id="default"),
        pytest.param({"PIP_INDEX_URL": "https://mirror.example/root/"}, "https://mirror.example/root/pip/", id="env"),
    ],
)
def test_yanked_files_asks_pypi_only_without_a_configured_index(
    mocker: MockerFixture, env: dict[str, str], expected: str
) -> None:
    opener: Final[MockType] = mocker.patch("virtualenv.seed.wheels.index.build_opener", autospec=True)
    opener.return_value.open.side_effect = URLError("offline")

    assert yanked_files("Pip", {**env, "PIP_CONFIG_FILE": os.devnull}) is None
    assert [call.args[0].full_url for call in opener.return_value.open.call_args_list] == [expected]


@pytest.mark.parametrize("value", ["y", "T", "true", "On", "1"])
def test_yanked_files_without_index_asks_nothing(mocker: MockerFixture, value: str) -> None:
    opener: Final[MockType] = mocker.patch("virtualenv.seed.wheels.index.build_opener", autospec=True)

    assert yanked_files("pip", {"PIP_NO_INDEX": value, "PIP_CONFIG_FILE": os.devnull}) is None
    opener.assert_not_called()


def test_yanked_files_reads_the_index_from_pip_configuration(tmp_path: Path) -> None:
    index: Final[str] = _file_index(tmp_path, {"pip-2.0-py3-none-any.whl": ""})
    config: Final[Path] = tmp_path / "pip.conf"
    config.write_text(f"[global]\nindex-url = file:///nowhere\n[download]\nindex_url = {index}\n", encoding="utf-8")

    assert yanked_files("pip", {"PIP_CONFIG_FILE": str(config)}) == {"pip-2.0-py3-none-any.whl"}


def test_yanked_files_environment_wins_over_configuration(tmp_path: Path) -> None:
    index: Final[str] = _file_index(tmp_path, {"pip-2.0-py3-none-any.whl": ""})
    config: Final[Path] = tmp_path / "pip.conf"
    config.write_text("[global]\nindex-url = file:///nowhere\n", encoding="utf-8")

    assert yanked_files("pip", {"PIP_CONFIG_FILE": str(config), "PIP_INDEX_URL": index}) == {"pip-2.0-py3-none-any.whl"}


@pytest.mark.parametrize(
    "user_file",
    [
        pytest.param(".pip/pip.conf", id="linux", marks=pytest.mark.skipif(sys.platform != "linux", reason="Linux")),
        pytest.param(
            ".config/pip/pip.conf", id="darwin", marks=pytest.mark.skipif(sys.platform != "darwin", reason="macOS")
        ),
        pytest.param("pip/pip.ini", id="win32", marks=pytest.mark.skipif(sys.platform != "win32", reason="Windows")),
    ],
)
def test_yanked_files_reads_the_per_user_configuration(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, user_file: str
) -> None:
    index: Final[str] = _file_index(tmp_path, {"pip-2.0-py3-none-any.whl": ""})
    home: Final[Path] = tmp_path / "home"
    (home / user_file).parent.mkdir(parents=True)
    (home / user_file).write_text(f"[global]\nindex-url = {index}\n", encoding="utf-8")
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    # hide the host's per-user pip folder
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))

    assert yanked_files("pip", {}) == {"pip-2.0-py3-none-any.whl"}


def test_yanked_files_config_file_variable_skips_per_user_configuration(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    index: Final[str] = _file_index(tmp_path, {"pip-2.0-py3-none-any.whl": ""})
    home: Final[Path] = tmp_path / "home"
    user_file: Final[Path] = home / ("pip/pip.ini" if sys.platform == "win32" else ".pip/pip.conf")
    user_file.parent.mkdir(parents=True)
    user_file.write_text("[global]\nno-index = true\n", encoding="utf-8")
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    config: Final[Path] = tmp_path / "pip.conf"
    config.write_text(f"[global]\nindex-url = {index}\n", encoding="utf-8")

    assert yanked_files("pip", {"PIP_CONFIG_FILE": str(config)}) == {"pip-2.0-py3-none-any.whl"}


@pytest.mark.skipif(sys.platform == "win32" or os.geteuid() == 0, reason="needs a folder the user may not enter")
def test_yanked_files_ignores_a_config_file_in_a_folder_it_may_not_enter(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    index: Final[str] = _file_index(tmp_path, {"pip-2.0-py3-none-any.whl": ""})
    locked: Final[Path] = tmp_path / "locked"
    locked.mkdir(mode=0)
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))

    result: Final[frozenset[str] | None] = yanked_files(
        "pip", {"PIP_INDEX_URL": index, "PIP_CONFIG_FILE": str(locked / "pip.conf")}
    )

    assert result == {"pip-2.0-py3-none-any.whl"}


def test_yanked_files_reads_the_index_without_a_home_folder(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    index: Final[str] = _file_index(tmp_path, {"pip-2.0-py3-none-any.whl": ""})
    _forget_home(monkeypatch, forget=True)
    # leaves only the legacy ~/.pip folder to resolve without a home
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))

    assert yanked_files("pip", {"PIP_INDEX_URL": index}) == {"pip-2.0-py3-none-any.whl"}


def _forget_home(monkeypatch: pytest.MonkeyPatch, forget: bool) -> None:
    if not forget:
        return
    for name in ("HOME", "USERPROFILE", "HOMEDRIVE", "HOMEPATH"):
        monkeypatch.delenv(name, raising=False)
    if sys.platform != "win32":
        monkeypatch.setattr("pwd.getpwuid", _no_passwd_entry)


def _no_passwd_entry(uid: int) -> NoReturn:
    raise KeyError(uid)


def test_yanked_files_reads_the_index_when_the_user_folders_are_unknown(tmp_path: Path, mocker: MockerFixture) -> None:
    index: Final[str] = _file_index(tmp_path, {"pip-2.0-py3-none-any.whl": ""})
    # as platformdirs does on macOS without a home folder, where XDG variables do not apply
    mocker.patch(
        "virtualenv.seed.wheels.index.user_config_dir",
        autospec=True,
        side_effect=RuntimeError("could not determine the home directory for '~/Library/Application Support'"),
    )

    assert yanked_files("pip", {"PIP_INDEX_URL": index}) == {"pip-2.0-py3-none-any.whl"}


@pytest.mark.parametrize("charset", ["utf8mb4", "base64", "zlib", "rot13"])
def test_yanked_files_reads_a_page_with_a_charset_it_cannot_decode_with(server: _Server, charset: str) -> None:
    html: Final[bytes] = _html({"pip-2.0-py3-none-any.whl": ""}).encode()
    server.pages["/simple/pip/"] = _Page(200, {"Content-Type": f"text/html; charset={charset}"}, html)

    result: Final[frozenset[str] | None] = yanked_files(
        "pip", {"PIP_INDEX_URL": f"{server.url}/simple/", "PIP_CONFIG_FILE": os.devnull}
    )

    assert result == {"pip-2.0-py3-none-any.whl"}


@pytest.mark.parametrize(
    ("page", "expected"),
    [
        pytest.param(
            '<a href="pip-2.0-py3-none-any.whl">x</a><a href="pip-2.0-py3-none-any.whl" data-yanked>x</a>',
            set(),
            id="html-one-listing-not-yanked",
        ),
        pytest.param(
            '<a href="pip-2.0-py3-none-any.whl" data-yanked>x</a><a href="pip-2.0-py3-none-any.whl">x</a>',
            set(),
            id="html-yanked-listing-first",
        ),
        pytest.param(
            '<a href="pip-2.0-py3-none-any.whl" data-yanked>x</a><a href="pip-2.0-py3-none-any.whl" data-yanked>x</a>',
            {"pip-2.0-py3-none-any.whl"},
            id="html-every-listing-yanked",
        ),
        pytest.param(
            '<a href="pip-2.0%2Blocal-py3-none-any.whl" data-yanked>x</a>',
            {"pip-2.0+local-py3-none-any.whl"},
            id="quoted",
        ),
    ],
)
def test_yanked_files_reads_each_listing_on_a_page(server: _Server, page: str, expected: set[str]) -> None:
    server.pages["/simple/pip/"] = _page(page)

    result: Final[frozenset[str] | None] = yanked_files(
        "pip", {"PIP_INDEX_URL": f"{server.url}/simple/", "PIP_CONFIG_FILE": os.devnull}
    )

    assert result == expected


@pytest.mark.parametrize(
    "order", [pytest.param((False, True), id="not-yanked-first"), pytest.param((True, False), id="yanked-first")]
)
def test_yanked_files_needs_every_json_listing_yanked(server: _Server, order: tuple[bool, bool]) -> None:
    files: Final[list[dict[str, str | bool]]] = [
        {"filename": "pip-2.0-py3-none-any.whl", "yanked": yanked} for yanked in order
    ]
    server.pages["/simple/pip/"] = _page(json.dumps({"files": files}), _JSON)

    result: Final[frozenset[str] | None] = yanked_files(
        "pip", {"PIP_INDEX_URL": f"{server.url}/simple/", "PIP_CONFIG_FILE": os.devnull}
    )

    assert result == frozenset()


def test_yanked_files_reads_a_page_whose_length_is_not_a_decimal_number(server: _Server) -> None:
    html: Final[bytes] = _html({"pip-2.0-py3-none-any.whl": ""}).encode()
    # str.isdigit accepts the superscript, which int() then refuses
    server.pages["/simple/pip/"] = _Page(200, {"Content-Type": "text/html", "Content-Length": "\u00b2"}, html)

    result: Final[frozenset[str] | None] = yanked_files(
        "pip", {"PIP_INDEX_URL": f"{server.url}/simple/", "PIP_CONFIG_FILE": os.devnull}
    )

    assert result == {"pip-2.0-py3-none-any.whl"}


@pytest.mark.parametrize(
    "error",
    [
        pytest.param(NotImplementedError("subclasses of ParserBase must override error()"), id="python-3.9"),
        pytest.param(AssertionError("unknown status keyword 'foo ' in marked section"), id="python-3.10-onwards"),
    ],
)
def test_yanked_files_reports_markup_the_parser_rejects_as_unknown(
    server: _Server, mocker: MockerFixture, error: Exception
) -> None:
    html: Final[str] = f"{_html({'pip-2.0-py3-none-any.whl': ''})}<![foo bar]>"
    server.pages["/simple/pip/"] = _Page(200, {"Content-Type": "text/html"}, html.encode())
    # html.parser before its 2025 hardening raised on such a marked section
    mocker.patch(
        "html.parser.HTMLParser.parse_html_declaration",
        autospec=True,
        side_effect=error,
    )

    assert yanked_files("pip", {"PIP_INDEX_URL": f"{server.url}/simple/", "PIP_CONFIG_FILE": os.devnull}) is None


def test_yanked_files_reads_a_chunked_page(server: _Server) -> None:
    html: Final[bytes] = _html({"pip-2.0-py3-none-any.whl": ""}).encode()
    chunked: Final[bytes] = f"{len(html):x}\r\n".encode() + html + b"\r\n0\r\n\r\n"
    # http.client ignores Content-Length on a chunked response, so the truncation check must too
    headers: Final[dict[str, str]] = {
        "Content-Type": "text/html",
        "Transfer-Encoding": "chunked",
        "Content-Length": "99999",
    }
    server.pages["/simple/pip/"] = _Page(200, headers, chunked)

    result: Final[frozenset[str] | None] = yanked_files(
        "pip", {"PIP_INDEX_URL": f"{server.url}/simple/", "PIP_CONFIG_FILE": os.devnull}
    )

    assert result == {"pip-2.0-py3-none-any.whl"}


def test_yanked_files_takes_the_password_for_a_url_user_from_netrc(server: _Server, tmp_path: Path) -> None:
    netrc_file: Final[Path] = tmp_path / "netrc"
    netrc_file.write_text("machine 127.0.0.1 login user password secret\n", encoding="utf-8")
    server.auth = f"Basic {b64encode(b'user:secret').decode()}"
    server.pages["/simple/pip/"] = _page(_html({"pip-2.0-py3-none-any.whl": ""}))
    index: Final[str] = f"http://user@{server.url.removeprefix('http://')}/simple/"

    result: Final[frozenset[str] | None] = yanked_files(
        "pip", {"PIP_INDEX_URL": index, "PIP_CONFIG_FILE": os.devnull, "NETRC": str(netrc_file)}
    )

    assert result == {"pip-2.0-py3-none-any.whl"}


class _Failure(NamedTuple):
    # values may name {url} (the loopback index), {tmp} (a scratch folder) and {tmp_uri} (that folder as a file URI)
    env: dict[str, str]
    files: tuple[tuple[str, bytes], ...] = ()
    page: _Page = _page(_html({"pip-2.0-py3-none-any.whl": ""}))
    auth: str | None = None
    homeless: bool = False


@pytest.mark.parametrize(
    "failure",
    [
        pytest.param(
            _Failure({"PIP_CONFIG_FILE": "{tmp}/pip.conf"}, (("pip.conf", b"index-url = no section\n"),)),
            id="config-without-section",
        ),
        # 0x81 is invalid in UTF-8 and undefined in cp1252, so no locale encoding decodes it
        pytest.param(
            _Failure({"PIP_CONFIG_FILE": "{tmp}/pip.conf"}, (("pip.conf", b"[global]\nindex-url = \x81\n"),)),
            id="config-undecodable",
        ),
        pytest.param(_Failure({"PIP_INDEX_URL": "http://[::1/simple/"}), id="url-unparsable"),
        pytest.param(
            _Failure({"PIP_INDEX_URL": "http://index.invalid/simple/", "PIP_PROXY": "{url}"}), id="proxy-without-page"
        ),
        pytest.param(_Failure({"PIP_INDEX_URL": "{tmp_uri}/missing/"}), id="index-folder-missing"),
        pytest.param(_Failure({"PIP_EXTRA_INDEX_URL": "{url}/missing/"}), id="extra-index-not-found"),
        pytest.param(_Failure({}, page=_Page(500, {}, b"")), id="server-error"),
        pytest.param(_Failure({}, auth="Basic never"), id="unauthorized"),
        pytest.param(
            _Failure({"NETRC": "{tmp}/netrc"}, (("netrc", b"machine\n"),), auth="Basic never"),
            id="netrc-malformed",
        ),
        # no HOME and no passwd entry, as in a container run under an arbitrary user id
        pytest.param(_Failure({}, auth="Basic never", homeless=True), id="home-unknown-for-netrc"),
        pytest.param(
            _Failure(
                {"PIP_INDEX_URL": "https://index.invalid/simple/", "PIP_CERT": "{tmp}/bundle.pem"},
                (("bundle.pem", b"not a certificate"),),
            ),
            id="certificate-bundle-invalid",
        ),
        pytest.param(
            _Failure({}, page=_Page(200, {"Content-Type": "text/html", "Content-Length": "100"}, b"<a")),
            id="body-truncated",
        ),
        pytest.param(_Failure({}, page=_page(" " * (16 * 1024 * 1024 + 1))), id="body-oversized"),
        pytest.param(_Failure({}, page=_page("{not json", _JSON)), id="json-invalid"),
        pytest.param(_Failure({}, page=_page("[]", _JSON)), id="json-not-an-object"),
        pytest.param(_Failure({}, page=_page(json.dumps({"meta": {}}), _JSON)), id="json-without-files"),
        pytest.param(_Failure({}, page=_page("[" * 100_000, _JSON)), id="json-nested-too-deep"),
    ],
)
def test_yanked_files_reports_every_failure_as_unknown(
    server: _Server,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    failure: _Failure,
) -> None:
    for name, content in failure.files:
        (tmp_path / name).write_bytes(content)
    server.pages["/simple/pip/"] = failure.page
    server.auth = failure.auth
    _forget_home(monkeypatch, failure.homeless)
    defaults: Final[dict[str, str]] = {"PIP_INDEX_URL": "{url}/simple/", "PIP_CONFIG_FILE": os.devnull}
    env: Final[dict[str, str]] = {
        key: value.format(url=server.url, tmp=tmp_path, tmp_uri=tmp_path.as_uri())
        for key, value in {**defaults, **failure.env}.items()
    }

    assert yanked_files("pip", env) is None
    assert "could not read" in caplog.text
