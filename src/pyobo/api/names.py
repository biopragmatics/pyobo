# -*- coding: utf-8 -*-

"""High-level API for nomenclature."""

import logging
from functools import lru_cache
from typing import Callable, List, Mapping, Optional, TypeVar

from .alts import get_primary_identifier
from .utils import get_version
from ..getters import NoBuild, get_ontology
from ..identifier_utils import normalize_curie, wrap_norm_prefix
from ..utils.cache import cached_mapping, cached_multidict, reverse_mapping
from ..utils.path import prefix_cache_join

__all__ = [
    "get_name",
    "get_name_by_curie",
    "get_id_name_mapping",
    "get_name_id_mapping",
    "get_definition",
    "get_id_definition_mapping",
    "get_synonyms",
    "get_id_synonyms_mapping",
]

logger = logging.getLogger(__name__)


def get_name_by_curie(curie: str) -> Optional[str]:
    """Get the name for a CURIE, if possible."""
    prefix, identifier = normalize_curie(curie)
    if prefix and identifier:
        return get_name(prefix, identifier)


X = TypeVar("X")


def _help_get(f: Callable[[str], Mapping[str, X]], prefix: str, identifier: str) -> Optional[X]:
    """Get the result for an entity based on a mapping maker function ``f``."""
    try:
        mapping = f(prefix)
    except NoBuild:
        mapping = None

    if not mapping:
        logger.warning("unable to look up results for prefix %s with %s", prefix, f)
        return

    primary_id = get_primary_identifier(prefix, identifier)
    return mapping.get(primary_id)


@wrap_norm_prefix
def get_name(prefix: str, identifier: str) -> Optional[str]:
    """Get the name for an entity."""
    return _help_get(get_id_name_mapping, prefix, identifier)


@lru_cache()
@wrap_norm_prefix
def get_id_name_mapping(prefix: str, force: bool = False, strict: bool = True) -> Mapping[str, str]:
    """Get an identifier to name mapping for the OBO file."""
    if prefix == "ncbigene":
        from ..sources.ncbigene import get_ncbigene_id_to_name_mapping

        logger.info("[%s] loading name mappings", prefix)
        rv = get_ncbigene_id_to_name_mapping()
        logger.info("[%s] done loading name mappings", prefix)
        return rv

    path = prefix_cache_join(prefix, name="names.tsv", version=get_version(prefix))

    @cached_mapping(path=path, header=[f"{prefix}_id", "name"], force=force)
    def _get_id_name_mapping() -> Mapping[str, str]:
        if force:
            logger.info("[%s] forcing reload for names", prefix)
        else:
            logger.info("[%s] no cached names found. getting from OBO loader", prefix)
        ontology = get_ontology(prefix, force=force, strict=strict)
        return ontology.get_id_name_mapping()

    return _get_id_name_mapping()


@lru_cache()
@wrap_norm_prefix
def get_name_id_mapping(prefix: str, force: bool = False) -> Mapping[str, str]:
    """Get a name to identifier mapping for the OBO file."""
    id_name = get_id_name_mapping(prefix=prefix, force=force)
    return reverse_mapping(id_name)


@wrap_norm_prefix
def get_definition(prefix: str, identifier: str) -> Optional[str]:
    """Get the definition for an entity."""
    return _help_get(get_id_definition_mapping, prefix, identifier)


def get_id_definition_mapping(prefix: str, force: bool = False) -> Mapping[str, str]:
    """Get a mapping of descriptions."""
    path = prefix_cache_join(prefix, name="definitions.tsv", version=get_version(prefix))

    @cached_mapping(path=path, header=[f"{prefix}_id", "definition"], force=force)
    def _get_mapping() -> Mapping[str, str]:
        logger.info("[%s] no cached descriptions found. getting from OBO loader", prefix)
        ontology = get_ontology(prefix, force=force)
        return ontology.get_id_definition_mapping()

    return _get_mapping()


@wrap_norm_prefix
def get_synonyms(prefix: str, identifier: str) -> Optional[List[str]]:
    """Get the synonyms for an entity."""
    return _help_get(get_id_synonyms_mapping, prefix, identifier)


@wrap_norm_prefix
def get_id_synonyms_mapping(prefix: str, force: bool = False) -> Mapping[str, List[str]]:
    """Get the OBO file and output a synonym dictionary."""
    path = prefix_cache_join(prefix, name="synonyms.tsv", version=get_version(prefix))

    @cached_multidict(path=path, header=[f"{prefix}_id", "synonym"], force=force)
    def _get_multidict() -> Mapping[str, List[str]]:
        logger.info("[%s] no cached synonyms found. getting from OBO loader", prefix)
        ontology = get_ontology(prefix, force=force)
        return ontology.get_id_synonyms_mapping()

    return _get_multidict()
