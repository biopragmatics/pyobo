"""High-level API for relations."""

import logging
from collections.abc import Mapping
from functools import lru_cache

import pandas as pd
from typing_extensions import Unpack

from .utils import get_version_from_kwargs
from ..constants import (
    RELATION_COLUMNS,
    RELATION_ID,
    RELATION_PREFIX,
    SOURCE_ID,
    SOURCE_PREFIX,
    TARGET_ID,
    TARGET_PREFIX,
    GetOntologyKwargs,
    check_should_cache,
    check_should_force,
    check_should_use_tqdm,
)
from ..getters import get_ontology
from ..identifier_utils import wrap_norm_prefix
from ..struct.reference import Reference
from ..struct.struct_utils import ReferenceHint, _ensure_ref
from ..utils.cache import cached_df
from ..utils.path import CacheArtifact, get_cache_path, get_relation_cache_path

__all__ = [
    "get_filtered_relations_df",
    "get_id_multirelations_mapping",
    "get_relation",
    "get_relation_mapping",
    "get_relations",
    "get_relations_df",
]

logger = logging.getLogger(__name__)


@wrap_norm_prefix
def get_relations(
    prefix: str, **kwargs: Unpack[GetOntologyKwargs]
) -> list[tuple[Reference, Reference, Reference]]:
    """Get relations."""
    df = get_relations_df(prefix, wide=False, **kwargs)
    return [
        (
            Reference(prefix=prefix, identifier=source_id),
            Reference(prefix=relation_prefix, identifier=relation_id),
            Reference(prefix=target_prefix, identifier=target_id),
        )
        for source_id, relation_prefix, relation_id, target_prefix, target_id in df.values
    ]


@wrap_norm_prefix
def get_relations_df(
    prefix: str, *, wide: bool = False, **kwargs: Unpack[GetOntologyKwargs]
) -> pd.DataFrame:
    """Get all relations from the OBO."""
    version = get_version_from_kwargs(prefix, kwargs)
    path = get_cache_path(prefix, CacheArtifact.relations, version=version)

    @cached_df(
        path=path, dtype=str, force=check_should_force(kwargs), cache=check_should_cache(kwargs)
    )
    def _df_getter() -> pd.DataFrame:
        ontology = get_ontology(prefix, **kwargs)
        return ontology.get_relations_df(use_tqdm=check_should_use_tqdm(kwargs))

    rv = _df_getter()

    if wide:
        rv = rv.rename(columns={f"{prefix}_id": SOURCE_ID})
        rv[SOURCE_PREFIX] = prefix
        rv = rv[RELATION_COLUMNS]

    return rv


@wrap_norm_prefix
def get_filtered_relations_df(
    prefix: str,
    relation: ReferenceHint,
    **kwargs: Unpack[GetOntologyKwargs],
) -> pd.DataFrame:
    """Get all the given relation."""
    relation = _ensure_ref(relation, ontology_prefix=prefix)
    version = get_version_from_kwargs(prefix, kwargs)
    all_relations_path = get_cache_path(prefix, CacheArtifact.relations, version=version)
    if all_relations_path.is_file():
        logger.debug("[%] loading all relations from %s", prefix, all_relations_path)
        df = pd.read_csv(all_relations_path, sep="\t", dtype=str)
        idx = (df[RELATION_PREFIX] == relation.prefix) & (df[RELATION_ID] == relation.identifier)
        columns = [f"{prefix}_id", TARGET_PREFIX, TARGET_ID]
        return df.loc[idx, columns]

    path = get_relation_cache_path(prefix, relation, version=version)

    @cached_df(
        path=path, dtype=str, force=check_should_force(kwargs), cache=check_should_cache(kwargs)
    )
    def _df_getter() -> pd.DataFrame:
        logger.info("[%s] no cached relations found. getting from OBO loader", prefix)
        ontology = get_ontology(prefix, **kwargs)
        return ontology.get_filtered_relations_df(relation, use_tqdm=check_should_use_tqdm(kwargs))

    return _df_getter()


@wrap_norm_prefix
def get_id_multirelations_mapping(
    prefix: str,
    typedef: ReferenceHint,
    **kwargs: Unpack[GetOntologyKwargs],
) -> Mapping[str, list[Reference]]:
    """Get the OBO file and output a synonym dictionary."""
    kwargs["version"] = get_version_from_kwargs(prefix, kwargs)
    ontology = get_ontology(prefix, **kwargs)
    return ontology.get_id_multirelations_mapping(
        typedef=typedef, use_tqdm=check_should_use_tqdm(kwargs)
    )


@lru_cache
@wrap_norm_prefix
def get_relation_mapping(
    prefix: str,
    relation: ReferenceHint,
    target_prefix: str,
    **kwargs: Unpack[GetOntologyKwargs],
) -> Mapping[str, str]:
    """Get relations from identifiers in the source prefix to target prefix with the given relation.

    .. warning:: Assumes there's only one version of the property for each term.

     Example usage: get homology between HGNC and MGI:

    >>> import pyobo
    >>> human_mapt_hgnc_id = "6893"
    >>> mouse_mapt_mgi_id = "97180"
    >>> hgnc_mgi_orthology_mapping = pyobo.get_relation_mapping("hgnc", "ro:HOM0000017", "mgi")
    >>> assert mouse_mapt_mgi_id == hgnc_mgi_orthology_mapping[human_mapt_hgnc_id]
    """
    ontology = get_ontology(prefix, **kwargs)
    return ontology.get_relation_mapping(
        relation=relation, target_prefix=target_prefix, use_tqdm=check_should_use_tqdm(kwargs)
    )


@wrap_norm_prefix
def get_relation(
    prefix: str,
    source_identifier: str,
    relation: ReferenceHint,
    target_prefix: str,
    **kwargs: Unpack[GetOntologyKwargs],
) -> str | None:
    """Get the target identifier corresponding to the given relationship from the source prefix/identifier pair.

    .. warning:: Assumes there's only one version of the property for each term.

     Example usage: get homology between MAPT in HGNC and MGI:

    >>> import pyobo
    >>> human_mapt_hgnc_id = "6893"
    >>> mouse_mapt_mgi_id = "97180"
    >>> assert mouse_mapt_mgi_id == pyobo.get_relation(
    ...     "hgnc", human_mapt_hgnc_id, "ro:HOM0000017", "mgi"
    ... )
    """
    relation_mapping = get_relation_mapping(
        prefix=prefix,
        relation=relation,
        target_prefix=target_prefix,
        **kwargs,
    )
    return relation_mapping.get(source_identifier)
