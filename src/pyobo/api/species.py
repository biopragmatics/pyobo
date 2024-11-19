"""High-level API for species."""

import logging
from collections.abc import Mapping
from functools import lru_cache

from typing_extensions import Unpack

from .alts import get_primary_identifier
from .utils import force_cache, kwargs_version
from ..constants import SlimLookupKwargs
from ..getters import NoBuildError, get_ontology
from ..identifier_utils import wrap_norm_prefix
from ..utils.cache import cached_mapping
from ..utils.path import prefix_cache_join

__all__ = [
    "get_id_species_mapping",
    "get_species",
]

logger = logging.getLogger(__name__)


@wrap_norm_prefix
def get_species(prefix: str, identifier: str, **kwargs: Unpack[SlimLookupKwargs]) -> str | None:
    """Get the species."""
    if prefix == "uniprot":
        raise NotImplementedError

    try:
        id_species = get_id_species_mapping(prefix, **kwargs)
    except NoBuildError:
        logger.warning("unable to look up species for prefix %s", prefix)
        return None

    if not id_species:
        logger.warning("no results produced for prefix %s", prefix)
        return None

    primary_id = get_primary_identifier(prefix, identifier, **kwargs)
    return id_species.get(primary_id)


@lru_cache
@wrap_norm_prefix
def get_id_species_mapping(prefix: str, **kwargs: Unpack[SlimLookupKwargs]) -> Mapping[str, str]:
    """Get an identifier to species mapping."""
    if prefix == "ncbigene":
        from ..sources.ncbigene import get_ncbigene_id_to_species_mapping

        logger.info("[%s] loading species mappings", prefix)
        rv = get_ncbigene_id_to_species_mapping()
        logger.info("[%s] done loading species mappings", prefix)
        return rv

    version = kwargs_version(prefix, kwargs)
    path = prefix_cache_join(prefix, name="species.tsv", version=version)

    @cached_mapping(path=path, header=[f"{prefix}_id", "species"], force=force_cache(kwargs))
    def _get_id_species_mapping() -> Mapping[str, str]:
        logger.info("[%s] no cached species found. getting from OBO loader", prefix)
        ontology = get_ontology(prefix, **kwargs)
        logger.info("[%s] loading species mappings", prefix)
        return ontology.get_id_species_mapping()

    return _get_id_species_mapping()
