"""Judge the licenses a virtualenv wheel or zipapp SBOM declares for what the artifact ships."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    from collections.abc import Iterator
    from typing import NotRequired, TypedDict

    class _Licensed(TypedDict):
        id: NotRequired[str]
        name: NotRequired[str]

    class _License(TypedDict):
        expression: NotRequired[str]
        license: NotRequired[_Licensed]

    _Component = TypedDict(
        "_Component",
        {
            "type": str,
            "bom-ref": str,
            "hashes": NotRequired[list[object]],
            "licenses": NotRequired[list[_License]],
            "components": NotRequired[list["_Component"]],
        },
    )

# the licensing policy in docs/development.rst refers to this set
ALLOWED_LICENSES: Final[frozenset[str]] = frozenset({
    "Apache-2.0",
    "BSD-2-Clause",
    "BSD-3-Clause",
    "ISC",
    "MIT",
    "PSF-2.0",
    "Unlicense",
})
# SPDX matches license ids without regard to case, and operators only in upper case
_ALLOWED_KEYS: Final[frozenset[str]] = frozenset(identifier.casefold() for identifier in ALLOWED_LICENSES)
_OPERATORS: Final[frozenset[str]] = frozenset({"AND", "OR", "WITH", "(", ")"})
_TOKEN: Final[re.Pattern[str]] = re.compile(r"[()]|[^\s()]+")


def license_problems(components: list[_Component]) -> list[str]:
    return [
        f"{component['bom-ref']}: {problem}" for component in _shipped(components) if (problem := _judge(component))
    ]


def _shipped(components: list[_Component]) -> Iterator[_Component]:
    for component in components:
        # the SBOM gives bytes only to what the artifact carries; a declared requirement resolves at install time, and a
        # library a seed wheel vendors ships under the terms of that wheel
        if component["type"] == "library" and (
            "hashes" in component or any(child["type"] == "file" for child in component.get("components", []))
        ):
            yield component
        yield from _shipped(component.get("components", []))


def _judge(component: _Component) -> str | None:
    licenses: Final[list[_License]] = component.get("licenses", [])
    terms: Final[list[str]] = [
        entry["expression"] if "expression" in entry else entry["license"]["id"]
        for entry in licenses
        if "expression" in entry or "id" in entry["license"]
    ]
    if not terms:
        if names := [entry["license"]["name"] for entry in licenses]:
            return f"declares license names {names} with no SPDX id; map them in hatch_build.py _CLASSIFIER_LICENSES"
        return "declares no license"
    try:
        denied: Final[list[str]] = [term for term in terms if not _allowed(term)]
    except ValueError as error:
        return str(error)
    if denied:
        return f"license {' AND '.join(denied)} is outside ALLOWED_LICENSES {sorted(ALLOWED_LICENSES)}"
    return None


def _allowed(expression: str) -> bool:
    tokens: Final[list[str]] = _TOKEN.findall(expression)[::-1]
    try:
        verdict: Final[bool] = _any_of(tokens)
    except ValueError as error:
        msg = f"license expression {expression!r} is malformed: {error}"
        raise ValueError(msg) from error
    if tokens:
        msg = f"license expression {expression!r} is malformed: unexpected {tokens[-1]!r}"
        raise ValueError(msg)
    return verdict


def _any_of(tokens: list[str]) -> bool:
    verdict = _all_of(tokens)
    while tokens and tokens[-1] == "OR":
        tokens.pop()
        verdict |= _all_of(tokens)
    return verdict


def _all_of(tokens: list[str]) -> bool:
    verdict = _term(tokens)
    while tokens and tokens[-1] == "AND":
        tokens.pop()
        verdict &= _term(tokens)
    return verdict


def _term(tokens: list[str]) -> bool:
    if (token := _pop(tokens)) == "(":
        verdict: Final[bool] = _any_of(tokens)
        if (closing := _pop(tokens)) != ")":
            msg = f"expected ')', got {closing!r}"
            raise ValueError(msg)
        return verdict
    if token in _OPERATORS:
        msg = f"unexpected {token!r}"
        raise ValueError(msg)
    # an exception grants extra permissions on top of the license it modifies, so that license alone decides
    if tokens and tokens[-1] == "WITH":
        tokens.pop()
        if (exception := _pop(tokens)) in _OPERATORS:
            msg = f"unexpected {exception!r}"
            raise ValueError(msg)
    return token.casefold() in _ALLOWED_KEYS


def _pop(tokens: list[str]) -> str:
    if not tokens:
        msg: Final[str] = "it ends early"
        raise ValueError(msg)
    return tokens.pop()


__all__ = [
    "ALLOWED_LICENSES",
    "license_problems",
]
