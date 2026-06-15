"""High-level API for metadata."""

import logging
from functools import lru_cache

from pystow.cache import CachedPydantic
from typing_extensions import Unpack

from .utils import get_version_from_kwargs
from ..constants import GetOntologyKwargs, check_should_force
from ..getters import get_ontology
from ..identifier_utils import wrap_norm_prefix
from ..struct.struct import VersionMetadata
from ..utils.path import CacheArtifact, get_cache_path

__all__ = [
    "get_metadata",
]

logger = logging.getLogger(__name__)


@lru_cache
@wrap_norm_prefix
def get_metadata(prefix: str, **kwargs: Unpack[GetOntologyKwargs]) -> VersionMetadata:
    """Get metadata for the ontology."""
    version = get_version_from_kwargs(prefix, kwargs)
    path = get_cache_path(prefix, CacheArtifact.metadata, version=version)

    @CachedPydantic(path=path, force=check_should_force(kwargs), model_cls=VersionMetadata)
    def _inner() -> VersionMetadata:
        ontology = get_ontology(prefix, **kwargs)
        return ontology.get_metadata()

    return _inner()
