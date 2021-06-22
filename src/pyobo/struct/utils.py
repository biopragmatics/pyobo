# -*- coding: utf-8 -*-

"""Utilities for data structures for OBO."""

OBO_ESCAPE = {c: f"\\{c}" for c in ':,"\\()[]{}'}
OBO_ESCAPE[" "] = "\\W"


def obo_escape(string: str) -> str:
    """Escape all funny characters for OBO."""
    return "".join(OBO_ESCAPE.get(character, character) for character in string)


def comma_separate(elements) -> str:
    """Map a list to strings and make comma separated."""
    return ", ".join(map(str, elements))
