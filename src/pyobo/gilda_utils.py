"""PyOBO's Gilda utilities."""

from __future__ import annotations

import warnings
from collections.abc import Iterable, Sequence
from typing import TYPE_CHECKING, Any, cast

import ssslm
from ssslm import literal_mappings_to_gilda
from typing_extensions import Unpack

from pyobo.api import (
    get_literal_mappings,
    get_literal_mappings_subset,
)
from pyobo.constants import GetOntologyKwargs
from pyobo.struct.reference import Reference

if TYPE_CHECKING:
    import gilda

__all__ = [
    "get_gilda_term_subset",
    "get_gilda_terms",
    "get_grounder",
]


def get_grounder(*args: Any, **kwargs: Any) -> gilda.Grounder:
    """Get a grounder."""
    warnings.warn("use pyobo.ner.get_grounder", DeprecationWarning, stacklevel=2)
    import pyobo.ner

    grounder = cast(ssslm.ner.GildaGrounder, pyobo.get_grounder(*args, **kwargs))
    return grounder._grounder


def get_gilda_terms(prefix: str, *, skip_obsolete: bool = False, **kwargs) -> Iterable[gilda.Term]:
    """Get gilda terms."""
    warnings.warn(
        "use pyobo.get_literal_mappings() directly and convert to gilda yourself",
        DeprecationWarning,
        stacklevel=2,
    )
    yield from literal_mappings_to_gilda(
        get_literal_mappings(prefix, skip_obsolete=skip_obsolete, **kwargs)
    )


def get_gilda_term_subset(
    source: str,
    ancestors: str | Sequence[str],
    *,
    skip_obsolete: bool = False,
    **kwargs: Unpack[GetOntologyKwargs],
) -> Iterable[gilda.Term]:
    """Get a subset of terms."""
    warnings.warn(
        "use pyobo.get_literal_mappings_subset() directly and convert to gilda yourself",
        DeprecationWarning,
        stacklevel=2,
    )
    if isinstance(ancestors, str):
        ancestors = [ancestors]

    yield from literal_mappings_to_gilda(
        get_literal_mappings_subset(
            source,
            ancestors=[Reference.from_curie(a) for a in ancestors],
            skip_obsolete=skip_obsolete,
            **kwargs,
        )
    )
