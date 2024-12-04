"""Get FamPlex xrefs."""

import logging
from collections.abc import Mapping
from functools import lru_cache

import bioregistry
import pandas as pd

from ...constants import (
    PROVENANCE,
    SOURCE_ID,
    SOURCE_PREFIX,
    TARGET_ID,
    TARGET_PREFIX,
    XREF_COLUMNS,
)
from ...utils.path import ensure_df

__all__ = [
    "get_famplex_xrefs_df",
]

logger = logging.getLogger(__name__)

URL = "https://github.com/sorgerlab/famplex/raw/master/equivalences.csv"


def _get_famplex_df(force: bool = False) -> pd.DataFrame:
    return ensure_df(
        prefix="fplx",
        url=URL,
        force=force,
        header=None,
        names=[TARGET_PREFIX, TARGET_ID, SOURCE_ID],
        sep=",",
    )


def get_famplex_xrefs_df(force: bool = False) -> pd.DataFrame:
    """Get xrefs from FamPlex."""
    df = _get_famplex_df(force=force)
    df[TARGET_PREFIX] = df[TARGET_PREFIX].map(bioregistry.normalize_prefix)
    df = df[df[TARGET_PREFIX].notna()]
    df[SOURCE_PREFIX] = "fplx"
    df[PROVENANCE] = "https://github.com/sorgerlab/famplex/raw/master/equivalences.csv"
    df = df[XREF_COLUMNS]
    return df


@lru_cache
def get_remapping(force: bool = False) -> Mapping[tuple[str, str], tuple[str, str, str]]:
    """Get a mapping from database/identifier pairs to famplex identifiers."""
    df = _get_famplex_df(force=force)
    rv = {}
    for target_ns, target_id, source_id in df.values:
        if target_ns.lower() == "medscan":
            continue  # MEDSCAN is proprietary and Ben said to skip using these identifiers
        remapped_prefix = bioregistry.normalize_prefix(target_ns)
        if remapped_prefix is None:
            logger.warning("could not remap %s", target_ns)
        else:
            rv[remapped_prefix, target_id] = "fplx", source_id, source_id
    return rv
