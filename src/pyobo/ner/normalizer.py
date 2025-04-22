"""Use synonyms from OBO to normalize names."""

from __future__ import annotations

from collections.abc import Iterable

from .api import get_grounder
from ..struct import Reference

__all__ = [
    "ground",
]


def ground(prefix: str | Iterable[str], query: str) -> Reference | None:
    """Normalize a string given the prefix's labels and synonyms.

    :param prefix: If a string, only grounds against that namespace. If a list, will try grounding
        against all in that order
    :param query: The string to try grounding
    """
    if isinstance(prefix, str):
        normalizer = get_grounder(prefix)
        match = normalizer.get_best_match(query)
        if match:
            return match.reference
    else:
        for p in prefix:
            if rv := ground(p, query):
                return rv
    return None
