# -*- coding: utf-8 -*-

"""High-level API for synonyms."""

import logging
import os
from functools import lru_cache
from typing import Mapping, Optional

import pandas as pd

from .utils import get_version
from ..constants import TARGET_ID, TARGET_PREFIX
from ..getters import get_ontology
from ..identifier_utils import wrap_norm_prefix
from ..utils.cache import cached_df, cached_mapping
from ..utils.path import prefix_cache_join

__all__ = [
    "get_xrefs_df",
    "get_filtered_xrefs",
    "get_xref",
]

logger = logging.getLogger(__name__)


@wrap_norm_prefix
def get_xref(prefix: str, identifier: str, new_prefix: str, flip: bool = False) -> Optional[str]:
    """Get the xref with the new prefix if a direct path exists."""
    filtered_xrefs = get_filtered_xrefs(prefix, new_prefix, flip=flip)
    return filtered_xrefs.get(identifier)


@lru_cache()
@wrap_norm_prefix
def get_filtered_xrefs(
    prefix: str,
    xref_prefix: str,
    flip: bool = False,
    *,
    use_tqdm: bool = False,
    force: bool = False,
) -> Mapping[str, str]:
    """Get xrefs to a given target."""
    path = prefix_cache_join(
        prefix, "xrefs", name=f"{xref_prefix}.tsv", version=get_version(prefix)
    )
    all_xrefs_path = prefix_cache_join(prefix, name="xrefs.tsv", version=get_version(prefix))
    header = [f"{prefix}_id", f"{xref_prefix}_id"]

    @cached_mapping(path=path, header=header, use_tqdm=use_tqdm, force=force)
    def _get_mapping() -> Mapping[str, str]:
        if os.path.exists(all_xrefs_path):
            logger.info("[%s] loading pre-cached xrefs", prefix)
            df = pd.read_csv(all_xrefs_path, sep="\t", dtype=str)
            logger.info("[%s] filtering pre-cached xrefs", prefix)
            df = df.loc[df[TARGET_PREFIX] == xref_prefix, [f"{prefix}_id", TARGET_ID]]
            return dict(df.values)

        logger.info("[%s] no cached xrefs found. getting from OBO loader", prefix)
        ontology = get_ontology(prefix, force=force)
        return ontology.get_filtered_xrefs_mapping(xref_prefix, use_tqdm=use_tqdm)

    rv = _get_mapping()
    if flip:
        return {v: k for k, v in rv.items()}
    return rv


@wrap_norm_prefix
def get_xrefs_df(
    prefix: str, *, use_tqdm: bool = False, force: bool = False, strict: bool = False
) -> pd.DataFrame:
    """Get all xrefs."""
    path = prefix_cache_join(prefix, name="xrefs.tsv", version=get_version(prefix))

    @cached_df(path=path, dtype=str, force=force)
    def _df_getter() -> pd.DataFrame:
        logger.info("[%s] no cached xrefs found. getting from OBO loader", prefix)
        ontology = get_ontology(prefix, force=force, strict=strict)
        return ontology.get_xrefs_df(use_tqdm=use_tqdm)

    return _df_getter()
