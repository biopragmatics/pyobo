"""High-level API for typedefs."""

import logging
from functools import lru_cache

import pandas as pd
from typing_extensions import Unpack

from .utils import get_version_from_kwargs
from ..constants import GetOntologyKwargs, check_should_cache, check_should_force
from ..getters import get_ontology
from ..identifier_utils import wrap_norm_prefix
from ..utils.cache import cached_df
from ..utils.path import CacheArtifact, get_cache_path

__all__ = [
    "get_typedef_df",
]

logger = logging.getLogger(__name__)


@lru_cache
@wrap_norm_prefix
def get_typedef_df(prefix: str, **kwargs: Unpack[GetOntologyKwargs]) -> pd.DataFrame:
    """Get an identifier to name mapping for the typedefs in an OBO file."""
    version = get_version_from_kwargs(prefix, kwargs)
    path = get_cache_path(prefix, CacheArtifact.typedefs, version=version)

    @cached_df(
        path=path, dtype=str, force=check_should_force(kwargs), cache=check_should_cache(kwargs)
    )
    def _df_getter() -> pd.DataFrame:
        logger.debug("[%s] no cached typedefs found. getting from OBO loader", prefix)
        ontology = get_ontology(prefix, **kwargs)
        logger.debug("[%s] loading typedef mappings", prefix)
        return ontology.get_typedef_df()

    return _df_getter()
