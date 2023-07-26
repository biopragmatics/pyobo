# -*- coding: utf-8 -*-

"""High-level API for nomenclature."""

import logging
import subprocess
import zipfile
from functools import lru_cache
from typing import Callable, List, Mapping, Optional, Set, TypeVar

from .alts import get_primary_identifier
from .utils import get_version
from ..getters import NoBuild, get_ontology
from ..identifier_utils import normalize_curie, wrap_norm_prefix
from ..utils.cache import cached_collection, cached_mapping, cached_multidict
from ..utils.path import prefix_cache_join

__all__ = [
    "get_name",
    "get_name_by_curie",
    "get_ids",
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
    return None


X = TypeVar("X")

NO_BUILD_PREFIXES = set()


def _help_get(
    f: Callable[[str], Mapping[str, X]],
    prefix: str,
    identifier: str,
    force: bool = False,
    strict: bool = False,
    version: Optional[str] = None,
) -> Optional[X]:
    """Get the result for an entity based on a mapping maker function ``f``."""
    try:
        mapping = f(prefix, force=force, strict=strict, version=version)  # type:ignore
    except NoBuild:
        if prefix not in NO_BUILD_PREFIXES:
            logger.warning("[%s] unable to look up results with %s", prefix, f)
            NO_BUILD_PREFIXES.add(prefix)
        return None

    if not mapping:
        if prefix not in NO_BUILD_PREFIXES:
            logger.warning("[%s] no results produced with %s", prefix, f)
            NO_BUILD_PREFIXES.add(prefix)
        return None

    primary_id = get_primary_identifier(prefix, identifier)
    return mapping.get(primary_id)


@wrap_norm_prefix
def get_name(prefix: str, identifier: str) -> Optional[str]:
    """Get the name for an entity."""
    return _help_get(get_id_name_mapping, prefix, identifier)


@lru_cache()
@wrap_norm_prefix
def get_ids(
    prefix: str, force: bool = False, strict: bool = False, version: Optional[str] = None
) -> Set[str]:
    """Get the set of identifiers for this prefix."""
    if prefix == "ncbigene":
        from ..sources.ncbigene import get_ncbigene_ids

        logger.info("[%s] loading name mappings", prefix)
        rv = get_ncbigene_ids()
        logger.info("[%s] done loading name mappings", prefix)
        return rv

    if version is None:
        version = get_version(prefix)
    path = prefix_cache_join(prefix, name="ids.tsv", version=version)

    @cached_collection(path=path, force=force)
    def _get_ids() -> Set[str]:
        if force:
            logger.info("[%s v%s] forcing reload for names", prefix, version)
        else:
            logger.debug(
                "[%s v%s] no cached identifiers found. getting from OBO loader", prefix, version
            )
        ontology = get_ontology(prefix, force=force, strict=strict, version=version)
        return ontology.get_ids()

    return set(_get_ids())


@lru_cache()
@wrap_norm_prefix
def get_id_name_mapping(
    prefix: str, *, force: bool = False, strict: bool = False, version: Optional[str] = None
) -> Mapping[str, str]:
    """Get an identifier to name mapping for the OBO file."""
    if prefix == "ncbigene":
        from ..sources.ncbigene import get_ncbigene_id_to_name_mapping

        logger.info("[%s] loading name mappings", prefix)
        rv = get_ncbigene_id_to_name_mapping()
        logger.info("[%s] done loading name mappings", prefix)
        return rv

    if version is None:
        version = get_version(prefix)
    path = prefix_cache_join(prefix, name="names.tsv", version=version)

    @cached_mapping(path=path, header=[f"{prefix}_id", "name"], force=force)
    def _get_id_name_mapping() -> Mapping[str, str]:
        if force:
            logger.debug("[%s v%s] forcing reload for names", prefix, version)
        else:
            logger.debug("[%s v%s] no cached names found. getting from OBO loader", prefix, version)
        ontology = get_ontology(prefix, force=force, strict=strict, version=version)
        return ontology.get_id_name_mapping()

    try:
        return _get_id_name_mapping()
    except (zipfile.BadZipFile, subprocess.CalledProcessError):
        logger.exception("[%s v%s] could not load", prefix, version)
        return {}


@lru_cache()
@wrap_norm_prefix
def get_name_id_mapping(prefix: str, force: bool = False) -> Mapping[str, str]:
    """Get a name to identifier mapping for the OBO file."""
    id_name = get_id_name_mapping(prefix=prefix, force=force)
    return {v: k for k, v in id_name.items()}


@wrap_norm_prefix
def get_definition(prefix: str, identifier: str) -> Optional[str]:
    """Get the definition for an entity."""
    return _help_get(get_id_definition_mapping, prefix, identifier)


def get_id_definition_mapping(
    prefix: str,
    *,
    force: bool = False,
    strict: bool = False,
    version: Optional[str] = None,
) -> Mapping[str, str]:
    """Get a mapping of descriptions."""
    if version is None:
        version = get_version(prefix)
    path = prefix_cache_join(prefix, name="definitions.tsv", version=version)

    @cached_mapping(path=path, header=[f"{prefix}_id", "definition"], force=force)
    def _get_mapping() -> Mapping[str, str]:
        logger.info(
            "[%s v%s] no cached descriptions found. getting from OBO loader", prefix, version
        )
        ontology = get_ontology(prefix, force=force, strict=strict, version=version)
        return ontology.get_id_definition_mapping()

    return _get_mapping()


@wrap_norm_prefix
def get_synonyms(prefix: str, identifier: str) -> Optional[List[str]]:
    """Get the synonyms for an entity."""
    return _help_get(get_id_synonyms_mapping, prefix, identifier)


@wrap_norm_prefix
def get_id_synonyms_mapping(
    prefix: str,
    *,
    force: bool = False,
    strict: bool = False,
    version: Optional[str] = None,
) -> Mapping[str, List[str]]:
    """Get the OBO file and output a synonym dictionary."""
    if version is None:
        version = get_version(prefix)
    path = prefix_cache_join(prefix, name="synonyms.tsv", version=version)

    @cached_multidict(path=path, header=[f"{prefix}_id", "synonym"], force=force)
    def _get_multidict() -> Mapping[str, List[str]]:
        logger.info("[%s v%s] no cached synonyms found. getting from OBO loader", prefix, version)
        ontology = get_ontology(prefix, force=force, strict=strict, version=version)
        return ontology.get_id_synonyms_mapping()

    return _get_multidict()
