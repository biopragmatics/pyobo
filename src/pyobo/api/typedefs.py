"""High-level API for typedefs."""

import logging
from functools import lru_cache
from typing import Optional

import pandas as pd

from .utils import get_version
from ..getters import get_ontology
from ..identifier_utils import wrap_norm_prefix
from ..utils.cache import cached_df
from ..utils.path import prefix_cache_join

__all__ = [
    "get_typedef_df",
]

logger = logging.getLogger(__name__)


@lru_cache
@wrap_norm_prefix
def get_typedef_df(
    prefix: str, *, force: bool = False, version: Optional[str] = None
) -> pd.DataFrame:
    """Get an identifier to name mapping for the typedefs in an OBO file."""
    if version is None:
        version = get_version(prefix)
    path = prefix_cache_join(prefix, name="typedefs.tsv", version=version)

    @cached_df(path=path, dtype=str, force=force)
    def _df_getter() -> pd.DataFrame:
        logger.debug("[%s] no cached typedefs found. getting from OBO loader", prefix)
        ontology = get_ontology(prefix, force=force, version=version)
        logger.debug("[%s] loading typedef mappings", prefix)
        return ontology.get_typedef_df()

    return _df_getter()
