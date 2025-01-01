"""Utilities for data structures for OBO."""

from __future__ import annotations

from collections.abc import Iterable
from typing import TypeAlias

__all__ = [
    "OBO_ESCAPE",
    "OBO_ESCAPE_SLIM",
    "TurtlePredicates",
    "obo_escape",
    "obo_escape_slim",
    "turtle_predicates_to_lines",
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


def turtle_quote(s: str) -> str:
    """Escape a string and quote it for turtle."""
    return f'"{_turtle_escape(s)}"'


def _turtle_escape(s: str) -> str:
    return s.replace('"', '\\"')


TurtlePredicates: TypeAlias = list[tuple[str, str | list[str]]]


def turtle_predicates_to_lines(identifier, turtle_predicates: TurtlePredicates) -> Iterable[str]:
    """Yield lines from turtle predicates."""
    if len(turtle_predicates) == 0:
        raise ValueError
    elif len(turtle_predicates) == 1:
        pred, values = turtle_predicates[0]
        if isinstance(values, list) and len(values) == 1:
            values = values[0]
        if isinstance(values, str):
            pass
        else:
            ", ".join(values)
        yield f"{identifier} {pred} {values} ."
    else:
        first, *middles, last = turtle_predicates
        yield f"{identifier} {first[0]} {_handle_os(first[1])} ;"
        for pred, values in middles:
            yield f"    {pred} {_handle_os(values)} ;"
        yield f"    {last[0]} {_handle_os(last[1])} ."


def _handle_os(values: str | list[str]) -> str:
    if isinstance(values, list) and len(values) == 1:
        values = values[0]
    if isinstance(values, str):
        return values
    else:
        return ", ".join(values)
