"""High-level API for metadata."""

import logging
from functools import lru_cache
from typing import Any, cast

from typing_extensions import Unpack

from .utils import get_version_from_kwargs
from ..constants import GetOntologyKwargs, check_should_force
from ..getters import get_ontology
from ..identifier_utils import wrap_norm_prefix
from ..utils.cache import cached_json
from ..utils.path import CacheArtifact, get_cache_path

__all__ = [
    "get_metadata",
]

logger = logging.getLogger(__name__)


@lru_cache
@wrap_norm_prefix
def get_metadata(prefix: str, **kwargs: Unpack[GetOntologyKwargs]) -> dict[str, Any]:
    """Get metadata for the ontology."""
    version = get_version_from_kwargs(prefix, kwargs)
    path = get_cache_path(prefix, CacheArtifact.metadata, version=version)

    @cached_json(path=path, force=check_should_force(kwargs))
    def _get_json() -> dict[str, Any]:
        ontology = get_ontology(prefix, **kwargs)
        return ontology.get_metadata()

    return cast(dict[str, Any], _get_json())
