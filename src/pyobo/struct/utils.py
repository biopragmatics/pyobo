"""Utilities for data structures for OBO."""

from __future__ import annotations

from collections.abc import Iterable

__all__ = [
    "OBO_ESCAPE",
    "OBO_ESCAPE_SLIM",
    "obo_escape",
    "obo_escape_slim",
]

OBO_ESCAPE_SLIM = {c: f"\\{c}" for c in ':,"\\()[]{}'}
OBO_ESCAPE = {" ": "\\W", **OBO_ESCAPE_SLIM}


def obo_escape(string: str) -> str:
    """Escape all funny characters for OBO."""
    return "".join(OBO_ESCAPE.get(character, character) for character in string)


def obo_escape_slim(string: str) -> str:
    """Escape all funny characters for OBO."""
    rv = "".join(OBO_ESCAPE_SLIM.get(character, character) for character in string)
    rv = rv.replace("\n", "\\n")
    return rv


def _bool_to_obo(v: bool) -> str:
    return "true" if v else "false"


def _boolean_tag(tag: str, bv: bool | None) -> Iterable[str]:
    if bv is not None:
        yield f"{tag}: {_bool_to_obo(bv)}"
