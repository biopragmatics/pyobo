"""High-level API for metadata."""

import logging
from collections.abc import Mapping
from functools import lru_cache
from typing import Optional

from .utils import get_version
from ..getters import get_ontology
from ..identifier_utils import wrap_norm_prefix
from ..utils.cache import cached_json
from ..utils.path import prefix_cache_join

__all__ = [
    "get_metadata",
]

logger = logging.getLogger(__name__)


@lru_cache
@wrap_norm_prefix
def get_metadata(
    prefix: str, *, force: bool = False, version: Optional[str] = None
) -> Mapping[str, str]:
    """Get metadata for the ontology."""
    if version is None:
        version = get_version(prefix)
    path = prefix_cache_join(prefix, name="metadata.json", version=version)

    @cached_json(path=path, force=force)
    def _get_json() -> Mapping[str, str]:
        if force:
            logger.debug("[%s] forcing reload for metadata", prefix)
        else:
            logger.debug("[%s] no cached metadata found. getting from OBO loader", prefix)
        ontology = get_ontology(prefix, force=force, version=version)
        return ontology.get_metadata()

    return _get_json()
