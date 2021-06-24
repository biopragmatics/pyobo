# -*- coding: utf-8 -*-

"""High-level API for species."""

import logging
from functools import lru_cache
from typing import Mapping, Optional

from .alts import get_primary_identifier
from .utils import get_version
from ..getters import NoBuild, get_ontology
from ..identifier_utils import wrap_norm_prefix
from ..utils.cache import cached_mapping
from ..utils.path import prefix_cache_join

__all__ = [
    "get_id_species_mapping",
    "get_species",
]

logger = logging.getLogger(__name__)


@wrap_norm_prefix
def get_species(prefix: str, identifier: str) -> Optional[str]:
    """Get the species."""
    if prefix == "uniprot":
        raise NotImplementedError

    try:
        id_species = get_id_species_mapping(prefix)
    except NoBuild:
        id_species = None

    if not id_species:
        logger.warning("unable to look up species for prefix %s", prefix)
        return

    primary_id = get_primary_identifier(prefix, identifier)
    return id_species.get(primary_id)


@lru_cache()
@wrap_norm_prefix
def get_id_species_mapping(prefix: str, force: bool = False) -> Mapping[str, str]:
    """Get an identifier to species mapping."""
    if prefix == "ncbigene":
        from ..sources.ncbigene import get_ncbigene_id_to_species_mapping

        logger.info("[%s] loading species mappings", prefix)
        rv = get_ncbigene_id_to_species_mapping()
        logger.info("[%s] done loading species mappings", prefix)
        return rv

    path = prefix_cache_join(prefix, name="species.tsv", version=get_version(prefix))

    @cached_mapping(path=path, header=[f"{prefix}_id", "species"], force=force)
    def _get_id_species_mapping() -> Mapping[str, str]:
        logger.info("[%s] no cached species found. getting from OBO loader", prefix)
        ontology = get_ontology(prefix, force=force)
        logger.info("[%s] loading species mappings", prefix)
        return ontology.get_id_species_mapping()

    return _get_id_species_mapping()
