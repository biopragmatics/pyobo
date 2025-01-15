"""High-level API for alternative identifiers."""

import logging
from collections.abc import Mapping
from functools import lru_cache

import curies
from typing_extensions import Unpack

from .utils import get_version_from_kwargs
from ..constants import GetOntologyKwargs, check_should_cache, check_should_force
from ..getters import get_ontology
from ..identifier_utils import wrap_norm_prefix
from ..struct.reference import Reference
from ..utils.cache import cached_multidict
from ..utils.path import prefix_cache_join

__all__ = [
    "get_alts_to_id",
    "get_id_to_alts",
    "get_primary_curie",
    "get_primary_identifier",
]

logger = logging.getLogger(__name__)

NO_ALTS = {
    "ncbigene",
}


@lru_cache
@wrap_norm_prefix
def get_id_to_alts(prefix: str, **kwargs: Unpack[GetOntologyKwargs]) -> Mapping[str, list[str]]:
    """Get alternate identifiers."""
    if prefix in NO_ALTS:
        return {}

    version = get_version_from_kwargs(prefix, kwargs)
    path = prefix_cache_join(prefix, name="alt_ids.tsv", version=version)

    @cached_multidict(
        path=path,
        header=[f"{prefix}_id", "alt_id"],
        cache=check_should_cache(kwargs),
        force=check_should_force(kwargs),
    )
    def _get_mapping() -> Mapping[str, list[str]]:
        ontology = get_ontology(prefix, **kwargs)
        return ontology.get_id_alts_mapping()

    return _get_mapping()


@lru_cache
@wrap_norm_prefix
def get_alts_to_id(prefix: str, **kwargs: Unpack[GetOntologyKwargs]) -> Mapping[str, str]:
    """Get alternative id to primary id mapping."""
    return {
        alt: primary for primary, alts in get_id_to_alts(prefix, **kwargs).items() for alt in alts
    }


def get_primary_curie(
    curie: str,
    **kwargs: Unpack[GetOntologyKwargs],
) -> str | None:
    """Get the primary curie for an entity."""
    reference = Reference.from_curie_or_uri(curie, strict=kwargs.get("strict", True))
    if reference is None:
        return None
    primary_identifier = get_primary_identifier(reference, **kwargs)
    return f"{reference.prefix}:{primary_identifier}"


@wrap_norm_prefix
def get_primary_identifier(
    prefix: str | curies.Reference | curies.ReferenceTuple,
    identifier: str | None = None,
    /,
    **kwargs: Unpack[GetOntologyKwargs],
) -> str:
    """Get the primary identifier for an entity.

    :param prefix: The name of the resource
    :param identifier: The identifier to look up
    :returns: the canonical identifier based on alt id lookup

    Returns the original identifier if there are no alts available or if there's no mapping.
    """
    if isinstance(prefix, curies.ReferenceTuple | curies.Reference):
        identifier = prefix.identifier
        prefix = prefix.prefix
    elif identifier is None:
        raise ValueError("passed a prefix but no local unique identifier")

    if prefix in NO_ALTS:  # TODO later expand list to other namespaces with no alts
        return identifier

    alts_to_id = get_alts_to_id(prefix, **kwargs)
    return alts_to_id.get(identifier, identifier)
