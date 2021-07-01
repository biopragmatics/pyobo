# -*- coding: utf-8 -*-

"""High-level API for relations."""

import logging
import os
from functools import lru_cache
from typing import List, Mapping, Optional

import pandas as pd

from .utils import get_version
from ..constants import (
    RELATION_COLUMNS,
    RELATION_ID,
    RELATION_PREFIX,
    SOURCE_ID,
    SOURCE_PREFIX,
    TARGET_ID,
    TARGET_PREFIX,
)
from ..getters import get_ontology
from ..identifier_utils import wrap_norm_prefix
from ..struct import Reference, RelationHint, TypeDef, get_reference_tuple
from ..utils.cache import cached_df
from ..utils.path import prefix_cache_join

# TODO get_relation, get_relations

logger = logging.getLogger(__name__)


@wrap_norm_prefix
def get_relations_df(
    prefix: str,
    *,
    use_tqdm: bool = False,
    force: bool = False,
    wide: bool = False,
) -> pd.DataFrame:
    """Get all relations from the OBO."""
    path = prefix_cache_join(prefix, name="relations.tsv", version=get_version(prefix))

    @cached_df(path=path, dtype=str, force=force)
    def _df_getter() -> pd.DataFrame:
        if force:
            logger.info("[%s] forcing reload for relations", prefix)
        else:
            logger.info("[%s] no cached relations found. getting from OBO loader", prefix)
        ontology = get_ontology(prefix, force=force)
        return ontology.get_relations_df(use_tqdm=use_tqdm)

    rv = _df_getter()

    if wide:
        rv = rv.rename(columns={f"{prefix}_id": SOURCE_ID})
        rv[SOURCE_PREFIX] = prefix
        rv = rv[RELATION_COLUMNS]

    return rv


@wrap_norm_prefix
def get_filtered_relations_df(
    prefix: str,
    relation: RelationHint,
    *,
    use_tqdm: bool = False,
    force: bool = False,
) -> pd.DataFrame:
    """Get all of the given relation."""
    relation_prefix, relation_identifier = relation = get_reference_tuple(relation)
    path = prefix_cache_join(
        prefix,
        "relations",
        name=f"{relation_prefix}:{relation_identifier}.tsv",
        version=get_version(prefix),
    )
    all_relations_path = prefix_cache_join(
        prefix, name="relations.tsv", version=get_version(prefix)
    )

    @cached_df(path=path, dtype=str, force=force)
    def _df_getter() -> pd.DataFrame:
        if os.path.exists(all_relations_path):
            logger.debug("[%] loading all relations from %s", prefix, all_relations_path)
            df = pd.read_csv(all_relations_path, sep="\t", dtype=str)
            idx = (df[RELATION_PREFIX] == relation_prefix) & (
                df[RELATION_ID] == relation_identifier
            )
            columns = [f"{prefix}_id", TARGET_PREFIX, TARGET_ID]
            return df.loc[idx, columns]

        logger.info("[%s] no cached relations found. getting from OBO loader", prefix)
        ontology = get_ontology(prefix, force=force)
        return ontology.get_filtered_relations_df(relation, use_tqdm=use_tqdm)

    return _df_getter()


@wrap_norm_prefix
def get_id_multirelations_mapping(
    prefix: str,
    typedef: TypeDef,
    *,
    use_tqdm: bool = False,
    force: bool = False,
) -> Mapping[str, List[Reference]]:
    """Get the OBO file and output a synonym dictionary."""
    ontology = get_ontology(prefix, force=force)
    return ontology.get_id_multirelations_mapping(typedef=typedef, use_tqdm=use_tqdm)


@lru_cache()
@wrap_norm_prefix
def get_relation_mapping(
    prefix: str,
    relation: RelationHint,
    target_prefix: str,
    *,
    use_tqdm: bool = False,
    force: bool = False,
) -> Mapping[str, str]:
    """Get relations from identifiers in the source prefix to target prefix with the given relation.

    .. warning:: Assumes there's only one version of the property for each term.

     Example usage: get homology between HGNC and MGI:

    >>> import pyobo
    >>> human_mapt_hgnc_id = '6893'
    >>> mouse_mapt_mgi_id = '97180'
    >>> hgnc_mgi_orthology_mapping = pyobo.get_relation_mapping('hgnc', 'ro:HOM0000017', 'mgi')
    >>> assert mouse_mapt_mgi_id == hgnc_mgi_orthology_mapping[human_mapt_hgnc_id]
    """
    ontology = get_ontology(prefix, force=force)
    return ontology.get_relation_mapping(
        relation=relation, target_prefix=target_prefix, use_tqdm=use_tqdm
    )


@wrap_norm_prefix
def get_relation(
    prefix: str,
    source_identifier: str,
    relation: RelationHint,
    target_prefix: str,
    *,
    use_tqdm: bool = False,
    force: bool = False,
) -> Optional[str]:
    """Get the target identifier corresponding to the given relationship from the source prefix/identifier pair.

    .. warning:: Assumes there's only one version of the property for each term.

     Example usage: get homology between MAPT in HGNC and MGI:

    >>> import pyobo
    >>> human_mapt_hgnc_id = '6893'
    >>> mouse_mapt_mgi_id = '97180'
    >>> assert mouse_mapt_mgi_id == pyobo.get_relation('hgnc', human_mapt_hgnc_id, 'ro:HOM0000017', 'mgi')
    """
    relation_mapping = get_relation_mapping(
        prefix=prefix,
        relation=relation,
        target_prefix=target_prefix,
        use_tqdm=use_tqdm,
        force=force,
    )
    return relation_mapping.get(source_identifier)
