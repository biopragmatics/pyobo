"""High-level API for species."""

import logging
from collections.abc import Mapping
from functools import lru_cache

import curies
from typing_extensions import Unpack

from .alts import get_primary_identifier
from .utils import _get_pi, get_version_from_kwargs
from ..constants import GetOntologyKwargs, check_should_force
from ..getters import NoBuildError, get_ontology
from ..identifier_utils import wrap_norm_prefix
from ..utils.cache import cached_mapping
from ..utils.path import CacheArtifact, get_cache_path

__all__ = [
    "get_id_species_mapping",
    "get_species",
]

logger = logging.getLogger(__name__)


def get_species(
    prefix: str | curies.Reference | curies.ReferenceTuple,
    identifier: str | None = None,
    /,
    **kwargs: Unpack[GetOntologyKwargs],
) -> str | None:
    """Get the species."""
    t = _get_pi(prefix, identifier)

    if t.prefix == "uniprot":
        raise NotImplementedError

    try:
        id_species = get_id_species_mapping(t.prefix, **kwargs)
    except NoBuildError:
        logger.warning("unable to look up species for prefix %s", t.prefix)
        return None

    if not id_species:
        logger.warning("no results produced for prefix %s", t.prefix)
        return None

    primary_id = get_primary_identifier(t, **kwargs)
    return id_species.get(primary_id)


@lru_cache
@wrap_norm_prefix
def get_id_species_mapping(prefix: str, **kwargs: Unpack[GetOntologyKwargs]) -> Mapping[str, str]:
    """Get an identifier to species mapping."""
    if prefix == "ncbigene":
        from ..sources.ncbigene import get_ncbigene_id_to_species_mapping

        logger.info("[%s] loading species mappings", prefix)
        rv = get_ncbigene_id_to_species_mapping()
        logger.info("[%s] done loading species mappings", prefix)
        return rv

    version = get_version_from_kwargs(prefix, kwargs)
    path = get_cache_path(prefix, CacheArtifact.species, version=version)

    @cached_mapping(path=path, header=[f"{prefix}_id", "species"], force=check_should_force(kwargs))
    def _get_id_species_mapping() -> Mapping[str, str]:
        logger.info("[%s] no cached species found. getting from OBO loader", prefix)
        ontology = get_ontology(prefix, **kwargs)
        logger.info("[%s] loading species mappings", prefix)
        return ontology.get_id_species_mapping()

    return _get_id_species_mapping()
