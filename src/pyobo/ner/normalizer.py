"""Use synonyms from OBO to normalize names."""

from __future__ import annotations

from collections.abc import Iterable

from typing_extensions import Unpack

from .api import get_grounder
from ..constants import GetOntologyKwargs
from ..struct import Reference

__all__ = [
    "ground",
]


def ground(
    prefix: str | Iterable[str], query: str, **kwargs: Unpack[GetOntologyKwargs]
) -> Reference | None:
    """Normalize a string given the prefix's labels and synonyms.

    :param prefix: If a string, only grounds against that namespace. If a list, will try grounding
        against all in that order
    :param query: The string to try grounding
    """
    grounder = get_grounder(prefix, **kwargs)
    match = grounder.get_best_match(query)
    if match:
        # TODO when generics are working, the grounder
        #  can be type annotated with the right reference
        return Reference.from_reference(match.reference)
    return None
