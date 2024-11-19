"""High-level API for nomenclature."""

from __future__ import annotations

import logging
import subprocess
from collections.abc import Callable, Mapping
from functools import lru_cache
from typing import TypeVar

from curies import Reference, ReferenceTuple
from typing_extensions import Unpack

from .alts import get_primary_identifier
from .utils import force_cache, get_version, kwargs_version
from ..constants import SlimLookupKwargs
from ..getters import NoBuildError, get_ontology
from ..identifier_utils import wrap_norm_prefix
from ..utils.cache import cached_collection, cached_mapping, cached_multidict
from ..utils.path import prefix_cache_join

__all__ = [
    "get_definition",
    "get_id_definition_mapping",
    "get_id_name_mapping",
    "get_id_synonyms_mapping",
    "get_ids",
    "get_name",
    "get_name_by_curie",
    "get_name_id_mapping",
    "get_obsolete",
    "get_synonyms",
]

logger = logging.getLogger(__name__)


def get_name_by_curie(curie: str, *, version: str | None = None) -> str | None:
    """Get the name for a CURIE, if possible."""
    reference = Reference.from_curie(curie)
    if version is None:
        version = get_version(reference.prefix)
    return get_name(reference, version=version)


X = TypeVar("X")

NO_BUILD_PREFIXES: set[str] = set()
NO_BUILD_LOGGED: set = set()


def _help_get(
    f: Callable[[str, Unpack[SlimLookupKwargs]], Mapping[str, X]],
    prefix: str,
    identifier: str,
    **kwargs: Unpack[SlimLookupKwargs],
) -> X | None:
    """Get the result for an entity based on a mapping maker function ``f``."""
    try:
        mapping = f(prefix, **kwargs)  # type:ignore
    except NoBuildError:
        if prefix not in NO_BUILD_PREFIXES:
            logger.warning("[%s] unable to look up results with %s", prefix, f)
            NO_BUILD_PREFIXES.add(prefix)
        return None
    except ValueError as e:
        if prefix not in NO_BUILD_PREFIXES:
            logger.warning("[%s] value error while looking up results with %s: %s", prefix, f, e)
            NO_BUILD_PREFIXES.add(prefix)
        return None

    if not mapping:
        if prefix not in NO_BUILD_PREFIXES:
            logger.warning("[%s] no results produced with %s", prefix, f)
            NO_BUILD_PREFIXES.add(prefix)
        return None

    primary_id = get_primary_identifier(prefix, identifier, **kwargs)
    return mapping.get(primary_id)


@wrap_norm_prefix
def get_name(
    prefix: str | Reference | ReferenceTuple,
    identifier: str | None = None,
    /,
    **kwargs: Unpack[SlimLookupKwargs],
) -> str | None:
    """Get the name for an entity."""
    if isinstance(prefix, ReferenceTuple | Reference):
        identifier = prefix.identifier
        prefix = prefix.prefix
    if identifier is None:
        raise ValueError("identifier is None")
    return _help_get(get_id_name_mapping, prefix=prefix, identifier=identifier, **kwargs)


@lru_cache
@wrap_norm_prefix
def get_ids(prefix: str, **kwargs: Unpack[SlimLookupKwargs]) -> set[str]:
    """Get the set of identifiers for this prefix."""
    if prefix == "ncbigene":
        from ..sources.ncbigene import get_ncbigene_ids

        logger.info("[%s] loading name mappings", prefix)
        rv = get_ncbigene_ids()
        logger.info("[%s] done loading name mappings", prefix)
        return rv

    version = kwargs_version(prefix, kwargs)
    path = prefix_cache_join(prefix, name="ids.tsv", version=version)

    @cached_collection(path=path, force=force_cache(kwargs))
    def _get_ids() -> list[str]:
        ontology = get_ontology(prefix, **kwargs)
        return sorted(ontology.get_ids())

    return set(_get_ids())


@lru_cache
@wrap_norm_prefix
def get_id_name_mapping(
    prefix: str,
    **kwargs: Unpack[SlimLookupKwargs],
) -> Mapping[str, str]:
    """Get an identifier to name mapping for the OBO file."""
    if prefix == "ncbigene":
        from ..sources.ncbigene import get_ncbigene_id_to_name_mapping

        logger.info("[%s] loading name mappings", prefix)
        rv = get_ncbigene_id_to_name_mapping()
        logger.info("[%s] done loading name mappings", prefix)
        return rv

    version = kwargs_version(prefix, kwargs)
    path = prefix_cache_join(prefix, name="names.tsv", version=version)

    @cached_mapping(path=path, header=[f"{prefix}_id", "name"], force=force_cache(kwargs))
    def _get_id_name_mapping() -> Mapping[str, str]:
        ontology = get_ontology(prefix, **kwargs)
        return ontology.get_id_name_mapping()

    try:
        return _get_id_name_mapping()
    except NoBuildError:
        logger.debug("[%s] no build", prefix)
        return {}
    except (Exception, subprocess.CalledProcessError) as e:
        logger.exception("[%s v%s] could not load: %s", prefix, version, e)
        return {}


@lru_cache
@wrap_norm_prefix
def get_name_id_mapping(
    prefix: str,
    **kwargs: Unpack[SlimLookupKwargs],
) -> Mapping[str, str]:
    """Get a name to identifier mapping for the OBO file."""
    id_name = get_id_name_mapping(prefix, **kwargs)
    return {v: k for k, v in id_name.items()}


@wrap_norm_prefix
def get_definition(
    prefix: str, identifier: str | None = None, **kwargs: Unpack[SlimLookupKwargs]
) -> str | None:
    """Get the definition for an entity."""
    if identifier is None:
        prefix, _, identifier = prefix.rpartition(":")
    if identifier is None:
        raise ValueError
    return _help_get(get_id_definition_mapping, prefix=prefix, identifier=identifier, **kwargs)


def get_id_definition_mapping(
    prefix: str,
    **kwargs: Unpack[SlimLookupKwargs],
) -> Mapping[str, str]:
    """Get a mapping of descriptions."""
    version = kwargs_version(prefix, kwargs)
    path = prefix_cache_join(prefix, name="definitions.tsv", version=version)

    @cached_mapping(path=path, header=[f"{prefix}_id", "definition"], force=force_cache(kwargs))
    def _get_mapping() -> Mapping[str, str]:
        logger.info(
            "[%s v%s] no cached descriptions found. getting from OBO loader", prefix, version
        )
        ontology = get_ontology(prefix, **kwargs)
        return ontology.get_id_definition_mapping()

    return _get_mapping()


def get_obsolete(prefix: str, **kwargs: Unpack[SlimLookupKwargs]) -> set[str]:
    """Get the set of obsolete local unique identifiers."""
    version = kwargs_version(prefix, kwargs)
    path = prefix_cache_join(prefix, name="obsolete.tsv", version=version)

    @cached_collection(path=path, force=force_cache(kwargs))
    def _get_obsolete() -> list[str]:
        ontology = get_ontology(prefix, **kwargs)
        return sorted(ontology.get_obsolete())

    return set(_get_obsolete())


@wrap_norm_prefix
def get_synonyms(
    prefix: str, identifier: str, **kwargs: Unpack[SlimLookupKwargs]
) -> list[str] | None:
    """Get the synonyms for an entity."""
    return _help_get(get_id_synonyms_mapping, prefix=prefix, identifier=identifier, **kwargs)


@wrap_norm_prefix
def get_id_synonyms_mapping(
    prefix: str, **kwargs: Unpack[SlimLookupKwargs]
) -> Mapping[str, list[str]]:
    """Get the OBO file and output a synonym dictionary."""
    version = kwargs_version(prefix, kwargs)
    path = prefix_cache_join(prefix, name="synonyms.tsv", version=version)

    @cached_multidict(path=path, header=[f"{prefix}_id", "synonym"], force=force_cache(kwargs))
    def _get_multidict() -> Mapping[str, list[str]]:
        logger.info("[%s v%s] no cached synonyms found. getting from OBO loader", prefix, version)
        ontology = get_ontology(prefix, **kwargs)
        return ontology.get_id_synonyms_mapping()

    return _get_multidict()
