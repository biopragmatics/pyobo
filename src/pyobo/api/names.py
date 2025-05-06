"""High-level API for nomenclature."""

from __future__ import annotations

import logging
import subprocess
from collections.abc import Callable, Mapping
from functools import lru_cache
from typing import Any, TypeVar

import curies
import pandas as pd
import ssslm
from pystow.cache import Cached
from ssslm import LiteralMapping
from typing_extensions import Unpack

from .alts import get_primary_identifier
from .utils import _get_pi, get_version_from_kwargs
from ..constants import (
    GetOntologyKwargs,
    check_should_cache,
    check_should_force,
)
from ..getters import NoBuildError, get_ontology
from ..identifier_utils import wrap_norm_prefix
from ..struct import Reference
from ..utils.cache import cached_collection, cached_df, cached_mapping
from ..utils.io import multidict
from ..utils.path import CacheArtifact, get_cache_path

__all__ = [
    "get_definition",
    "get_id_definition_mapping",
    "get_id_name_mapping",
    "get_id_synonyms_mapping",
    "get_ids",
    "get_literal_mappings",
    "get_literal_mappings_df",
    "get_name",
    "get_name_by_curie",
    "get_name_id_mapping",
    "get_obsolete",
    "get_obsolete_references",
    "get_references",
    "get_synonyms",
]

logger = logging.getLogger(__name__)


def get_name_by_curie(curie: str, **kwargs: Any) -> str | None:
    """Get the name for a CURIE, if possible."""
    return get_name(curie, **kwargs)


X = TypeVar("X")

NO_BUILD_PREFIXES: set[str] = set()
NO_BUILD_LOGGED: set = set()


def _help_get(
    f: Callable[[str, Unpack[GetOntologyKwargs]], Mapping[str, X]],
    reference: Reference,
    **kwargs: Unpack[GetOntologyKwargs],
) -> X | None:
    """Get the result for an entity based on a mapping maker function ``f``."""
    try:
        mapping = f(reference.prefix, **kwargs)  # type:ignore
    except NoBuildError:
        if reference.prefix not in NO_BUILD_PREFIXES:
            logger.warning("[%s] unable to look up results with %s", reference.prefix, f)
            NO_BUILD_PREFIXES.add(reference.prefix)
        return None
    except ValueError as e:
        if reference.prefix not in NO_BUILD_PREFIXES:
            logger.warning(
                "[%s] value error while looking up results with %s: %s", reference.prefix, f, e
            )
            NO_BUILD_PREFIXES.add(reference.prefix)
        return None

    if not mapping:
        if reference.prefix not in NO_BUILD_PREFIXES:
            logger.warning("[%s] no results produced with %s", reference.prefix, f)
            NO_BUILD_PREFIXES.add(reference.prefix)
        return None

    primary_id = get_primary_identifier(reference, **kwargs)
    return mapping.get(primary_id)


def get_name(
    prefix: str | curies.Reference | curies.ReferenceTuple,
    identifier: str | None = None,
    /,
    **kwargs: Unpack[GetOntologyKwargs],
) -> str | None:
    """Get the name for an entity."""
    reference = _get_pi(prefix, identifier)
    return _help_get(get_id_name_mapping, reference, **kwargs)


@lru_cache
@wrap_norm_prefix
def get_ids(prefix: str, **kwargs: Unpack[GetOntologyKwargs]) -> set[str]:
    """Get the set of identifiers for this prefix."""
    if prefix == "ncbigene":
        from ..sources.ncbi.ncbigene import get_ncbigene_ids

        logger.info("[%s] loading name mappings", prefix)
        rv = get_ncbigene_ids()
        logger.info("[%s] done loading name mappings", prefix)
        return rv

    return {
        reference.identifier
        for reference in get_references(prefix, **kwargs)
        if reference.prefix == prefix
    }


class CachedReferences(Cached[list[Reference]]):
    """Make a function lazily cache its return value as file."""

    def load(self) -> list[Reference]:
        """Load data from the cache as a list of strings.

        :returns: A list of strings loaded from the cache
        """
        with open(self.path) as file:
            return [Reference.from_curie(line.strip()) for line in file]

    def dump(self, references: list[Reference]) -> None:
        """Dump data to the cache as a list of strings.

        :param references: The list of strings to dump
        """
        with open(self.path, "w") as file:
            for reference in references:
                print(reference.curie, file=file)


@wrap_norm_prefix
def get_references(prefix: str, **kwargs: Unpack[GetOntologyKwargs]) -> set[Reference]:
    """Get the set of identifiers for this prefix."""
    if prefix == "ncbigene":
        from ..sources.ncbi.ncbigene import get_ncbigene_ids

        logger.info("[%s] loading identifiers ", prefix)
        rv = {Reference(prefix="ncbigene", identifier=i) for i in get_ncbigene_ids()}
        logger.info("[%s] done loading identifiers", prefix)
        return rv

    version = get_version_from_kwargs(prefix, kwargs)
    # TODO pre-cache these!
    path = get_cache_path(prefix, CacheArtifact.references, version=version)

    @CachedReferences(
        path=path,
        force=check_should_force(kwargs),
        cache=check_should_cache(kwargs),
    )
    def _get_references() -> list[Reference]:
        ontology = get_ontology(prefix, **kwargs)
        return sorted(ontology.iterate_references())

    return set(_get_references())


@lru_cache
@wrap_norm_prefix
def get_id_name_mapping(
    prefix: str,
    **kwargs: Unpack[GetOntologyKwargs],
) -> Mapping[str, str]:
    """Get an identifier to name mapping for the OBO file."""
    if prefix == "ncbigene":
        from ..sources.ncbi.ncbigene import get_ncbigene_id_to_name_mapping

        logger.info("[%s] loading identifiers", prefix)
        rv = get_ncbigene_id_to_name_mapping()
        logger.info("[%s] done loading identifiers", prefix)
        return rv

    version = get_version_from_kwargs(prefix, kwargs)
    path = get_cache_path(prefix, CacheArtifact.names, version=version)

    @cached_mapping(
        path=path,
        header=[f"{prefix}_id", "name"],
        force=check_should_force(kwargs),
        cache=check_should_cache(kwargs),
    )
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
    **kwargs: Unpack[GetOntologyKwargs],
) -> Mapping[str, str]:
    """Get a name to identifier mapping for the OBO file."""
    id_name = get_id_name_mapping(prefix, **kwargs)
    return {v: k for k, v in id_name.items()}


def get_definition(
    prefix: str | curies.Reference | curies.ReferenceTuple,
    identifier: str | None = None,
    /,
    **kwargs: Unpack[GetOntologyKwargs],
) -> str | None:
    """Get the definition for an entity."""
    reference = _get_pi(prefix, identifier)
    return _help_get(get_id_definition_mapping, reference, **kwargs)


def get_id_definition_mapping(
    prefix: str, **kwargs: Unpack[GetOntologyKwargs]
) -> Mapping[str, str]:
    """Get a mapping of descriptions."""
    version = get_version_from_kwargs(prefix, kwargs)
    path = get_cache_path(prefix, CacheArtifact.definitions, version=version)

    @cached_mapping(
        path=path,
        header=[f"{prefix}_id", "definition"],
        force=check_should_force(kwargs),
        cache=check_should_cache(kwargs),
    )
    def _get_mapping() -> Mapping[str, str]:
        logger.info(
            "[%s v%s] no cached descriptions found. getting from OBO loader", prefix, version
        )
        ontology = get_ontology(prefix, **kwargs)
        return ontology.get_id_definition_mapping()

    return _get_mapping()


@wrap_norm_prefix
def get_obsolete(prefix: str, **kwargs: Unpack[GetOntologyKwargs]) -> set[str]:
    """Get the set of obsolete local unique identifiers."""
    version = get_version_from_kwargs(prefix, kwargs)
    # TODO pre-cache these!
    path = get_cache_path(prefix, CacheArtifact.obsoletes, version=version)

    @cached_collection(
        path=path,
        force=check_should_force(kwargs),
        cache=check_should_cache(kwargs),
    )
    def _get_obsolete() -> list[str]:
        ontology = get_ontology(prefix, **kwargs)
        return sorted(ontology.get_obsolete())

    return set(_get_obsolete())


@wrap_norm_prefix
def get_obsolete_references(prefix: str, **kwargs: Unpack[GetOntologyKwargs]) -> set[Reference]:
    """Get the set of obsolete references."""
    return {
        Reference(prefix=prefix, identifier=identifier)
        for identifier in get_obsolete(prefix, **kwargs)
    }


def get_synonyms(
    prefix: str | curies.Reference | curies.ReferenceTuple,
    identifier: str | None = None,
    /,
    **kwargs: Unpack[GetOntologyKwargs],
) -> list[str] | None:
    """Get the synonyms for an entity."""
    reference = _get_pi(prefix, identifier)
    return _help_get(get_id_synonyms_mapping, reference, **kwargs)


@wrap_norm_prefix
def get_id_synonyms_mapping(
    prefix: str, **kwargs: Unpack[GetOntologyKwargs]
) -> Mapping[str, list[str]]:
    """Get the OBO file and output a synonym dictionary."""
    df = get_literal_mappings_df(prefix=prefix, **kwargs)
    prefix_with_colon = f"{prefix}:"
    prefix_with_colon_len = len(prefix_with_colon)
    # keep only literal mappings with the right prefix
    df = df[df["curie"].str.startswith(prefix_with_colon)]
    return multidict(
        (curie[prefix_with_colon_len:], text) for curie, text in df[["curie", "text"]].values
    )


def get_literal_mappings(
    prefix: str, *, skip_obsolete: bool = False, **kwargs: Unpack[GetOntologyKwargs]
) -> list[LiteralMapping]:
    """Get literal mappings."""
    df = get_literal_mappings_df(prefix=prefix, **kwargs)
    rv = ssslm.df_to_literal_mappings(df, reference_cls=Reference)
    if skip_obsolete:
        obsoletes = get_obsolete_references(prefix, **kwargs)
        rv = [lm for lm in rv if lm.reference not in obsoletes]
    return rv


def get_literal_mappings_df(
    prefix: str,
    **kwargs: Unpack[GetOntologyKwargs],
) -> pd.DataFrame:
    """Get a literal mappings dataframe."""
    version = get_version_from_kwargs(prefix, kwargs)
    path = get_cache_path(prefix, CacheArtifact.literal_mappings, version=version)

    @cached_df(
        path=path, dtype=str, force=check_should_force(kwargs), cache=check_should_cache(kwargs)
    )
    def _df_getter() -> pd.DataFrame:
        return get_ontology(prefix, **kwargs).get_literal_mappings_df()

    return _df_getter()
