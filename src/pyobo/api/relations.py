# -*- coding: utf-8 -*-

"""High-level API for relations."""

import logging
import os
from typing import List, Mapping

import pandas as pd

from .utils import get_version
from ..constants import (
    RELATION_COLUMNS, RELATION_ID, RELATION_PREFIX, SOURCE_ID, SOURCE_PREFIX, TARGET_ID,
    TARGET_PREFIX,
)
from ..getters import get
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
    path = prefix_cache_join(prefix, name='relations.tsv', version=get_version(prefix))

    @cached_df(path=path, dtype=str, force=force)
    def _df_getter() -> pd.DataFrame:
        if force:
            logger.info('[%s] forcing reload for relations', prefix)
        else:
            logger.info('[%s] no cached relations found. getting from OBO loader', prefix)
        obo = get(prefix, force=force)
        return obo.get_relations_df(use_tqdm=use_tqdm)

    rv = _df_getter()

    if wide:
        rv = rv.rename(columns={f'{prefix}_id': SOURCE_ID})
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
        prefix, 'relations', name=f'{relation_prefix}:{relation_identifier}.tsv', version=get_version(prefix),
    )
    all_relations_path = prefix_cache_join(prefix, name='relations.tsv', version=get_version(prefix))

    @cached_df(path=path, dtype=str, force=force)
    def _df_getter() -> pd.DataFrame:
        if os.path.exists(all_relations_path):
            logger.debug('[%] loading all relations from %s', prefix, all_relations_path)
            df = pd.read_csv(all_relations_path, sep='\t', dtype=str)
            idx = (df[RELATION_PREFIX] == relation_prefix) & (df[RELATION_ID] == relation_identifier)
            columns = [f'{prefix}_id', TARGET_PREFIX, TARGET_ID]
            return df.loc[idx, columns]

        logger.info('[%s] no cached relations found. getting from OBO loader', prefix)
        obo = get(prefix, force=force)
        return obo.get_filtered_relations_df(relation, use_tqdm=use_tqdm)

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
    obo = get(prefix, force=force)
    return obo.get_id_multirelations_mapping(typedef=typedef, use_tqdm=use_tqdm)
