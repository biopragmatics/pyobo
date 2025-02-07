"""Functions that combine other API aspects."""

from collections.abc import Sequence

import biosynonyms
import curies
from typing_extensions import Unpack

from pyobo.api.hierarchy import get_descendants
from pyobo.api.names import get_literal_mappings
from pyobo.constants import GetOntologyKwargs
from pyobo.struct.reference import Reference

__all__ = [
    "get_literal_mappings_subset",
]


def get_literal_mappings_subset(
    prefix: str,
    ancestors: curies.Reference | Sequence[curies.Reference],
    *,
    skip_obsolete: bool = False,
    **kwargs: Unpack[GetOntologyKwargs],
) -> list[biosynonyms.LiteralMapping]:
    """Get a subset of literal mappings under the given ancestors."""
    if isinstance(ancestors, curies.Reference):
        ancestors = [ancestors]

    subset: set[curies.Reference] = {
        Reference.from_curie(descendant)
        for ancestor in ancestors
        for descendant in get_descendants(ancestor, **kwargs) or []
    }
    return [
        literal_mapping
        for literal_mapping in get_literal_mappings(prefix, skip_obsolete=skip_obsolete, **kwargs)
        if literal_mapping.reference in subset
    ]
