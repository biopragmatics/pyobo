"""Utilities for data structures for OBO."""

__all__ = [
    "OBO_ESCAPE_SLIM",
    "OBO_ESCAPE",
    "obo_escape",
    "obo_escape_slim",
    "comma_separate",
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


def comma_separate(elements) -> str:
    """Map a list to strings and make comma separated."""
    return ", ".join(map(str, elements))
