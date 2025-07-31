"""High-level API for alternative identifiers."""

import logging
from collections.abc import Mapping
from functools import lru_cache

import curies
from pydantic import ValidationError
from typing_extensions import Unpack

from .utils import _get_pi, get_version_from_kwargs
from ..constants import GetOntologyKwargs, check_should_cache, check_should_force
from ..getters import get_ontology
from ..identifier_utils import wrap_norm_prefix
from ..utils.cache import cached_multidict
from ..utils.path import CacheArtifact, get_cache_path

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
    path = get_cache_path(prefix, CacheArtifact.alts, version=version)

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
    prefix: str | curies.Reference | curies.ReferenceTuple,
    identifier: str | None = None,
    /,
    **kwargs: Unpack[GetOntologyKwargs],
) -> str | None:
    """Get the primary curie for an entity."""
    reference = _get_pi(prefix, identifier)
    try:
        primary_identifier = get_primary_identifier(reference, **kwargs)
    except (ValueError, ValidationError):
        if kwargs.get("strict"):
            raise
        # this happens on invalid prefix. maybe revise?
        return None
    return f"{reference.prefix}:{primary_identifier}"


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

    Returns the original identifier if there are no alts available or if there's no
    mapping.
    """
    t = _get_pi(prefix, identifier)
    if t.prefix in NO_ALTS:  # TODO later expand list to other namespaces with no alts
        return t.identifier
    alts_to_id = get_alts_to_id(t.prefix, **kwargs)
    return alts_to_id.get(t.identifier, t.identifier)
