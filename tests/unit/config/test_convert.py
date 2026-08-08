from __future__ import annotations

import os

import pytest

from virtualenv.config.convert import BoolType, ListType, NoneType, TypeData, convert


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        pytest.param("a,b,c", ["a", "b", "c"], id="comma"),
        pytest.param("a\nb\nc", ["a", "b", "c"], id="newline"),
        pytest.param(" a , b ", ["a", "b"], id="strips_whitespace"),
        pytest.param("a\n\nb", ["a", "b"], id="drops_blank_lines"),
        pytest.param("", [], id="empty"),
        pytest.param("a", ["a"], id="single"),
        pytest.param("a\nb,c", ["a", "b,c"], id="newline_wins_over_comma"),
    ],
)
def test_split_values_str(value: str, expected: list[str]) -> None:
    assert ListType(list, str).split_values(value) == expected


def test_split_values_list_passthrough() -> None:
    assert ListType(list, str).split_values(["a", "b"]) == ["a", "b"]


@pytest.mark.parametrize("value", ["a,b", ["a", "b"]])
def test_split_values_returns_reusable_list(value: str | list[str]) -> None:
    # It used to hand back a filter object for str input, so a second pass
    # over the result came up empty and len() failed outright.
    result = ListType(list, str).split_values(value)

    assert isinstance(result, list)
    assert len(result) == 2
    assert list(result) == list(result)


def test_list_type_convert_splits_on_pathsep() -> None:
    value = os.pathsep.join(["a", "b"])
    assert ListType(list, str).convert(value) == ["a", "b"]


@pytest.mark.parametrize(("value", "expected"), [("1", True), ("yes", True), ("ON", True), ("0", False), ("no", False)])
def test_bool_type(value: str, expected: bool) -> None:
    assert BoolType(bool, bool).convert(value) is expected


def test_bool_type_invalid() -> None:
    with pytest.raises(ValueError, match="Not a boolean: maybe"):
        BoolType(bool, bool).convert("maybe")


@pytest.mark.parametrize(("value", "expected"), [("", None), ("a", "a")])
def test_none_type(value: str, expected: str | None) -> None:
    assert NoneType(type(None), str).convert(value) == expected


def test_convert_logs_and_reraises(caplog: pytest.LogCaptureFixture) -> None:
    with pytest.raises(ValueError, match="Not a boolean"):
        convert("maybe", BoolType(bool, bool), "some-source")

    assert "some-source failed to convert 'maybe'" in caplog.text


def test_type_data_repr() -> None:
    assert repr(TypeData(str, str)) == "TypeData(base=<class 'str'>, as=<class 'str'>)"
