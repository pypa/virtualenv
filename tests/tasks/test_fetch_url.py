from __future__ import annotations

import io
import runpy
import time
from email.message import Message
from pathlib import Path
from typing import TYPE_CHECKING, Final
from urllib.error import HTTPError, URLError

import pytest

if TYPE_CHECKING:
    from collections.abc import Callable

    from pytest_mock import MockerFixture

_CONTENT: Final[bytes] = b"wheel"
_URL: Final[str] = "https://files.example/demo-1.0-py3-none-any.whl"


def _http_error(code: int) -> HTTPError:
    return HTTPError(_URL, code, "error", Message(), None)


@pytest.fixture
def fetch(mocker: MockerFixture) -> Callable[[list[Exception | io.BytesIO]], bytes]:
    def invoke(responses: list[Exception | io.BytesIO]) -> bytes:
        mocker.patch("urllib.request.urlopen", autospec=True, side_effect=responses)
        fetch_function = runpy.run_path(str(Path(__file__).parents[2] / "tasks" / "fetch_url.py"))["fetch"]
        mocker.patch.dict(fetch_function.__globals__, {"time": mocker.create_autospec(time)})
        return fetch_function(_URL)

    return invoke


@pytest.mark.parametrize(
    "failure",
    [
        pytest.param(URLError("EOF occurred in violation of protocol"), id="dropped-connection"),
        pytest.param(TimeoutError("timed out"), id="timeout"),
        pytest.param(ConnectionResetError("reset"), id="reset"),
        pytest.param(_http_error(503), id="server-error"),
    ],
)
def test_fetch_retries_transient_failure(
    fetch: Callable[[list[Exception | io.BytesIO]], bytes], failure: Exception
) -> None:
    assert fetch([failure, failure, io.BytesIO(_CONTENT)]) == _CONTENT


def test_fetch_gives_up_after_three_failures(fetch: Callable[[list[Exception | io.BytesIO]], bytes]) -> None:
    with pytest.raises(URLError, match="third"):
        fetch([URLError("first"), URLError("second"), URLError("third"), io.BytesIO(_CONTENT)])


def test_fetch_does_not_retry_client_error(fetch: Callable[[list[Exception | io.BytesIO]], bytes]) -> None:
    with pytest.raises(HTTPError, match="error"):
        fetch([_http_error(404), io.BytesIO(_CONTENT)])
