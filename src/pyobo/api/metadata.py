"""High-level API for metadata."""

import logging
from functools import lru_cache
from typing import Any, cast

from typing_extensions import Unpack

from .utils import force_cache, kwargs_version
from ..constants import SlimLookupKwargs
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
def get_metadata(prefix: str, **kwargs: Unpack[SlimLookupKwargs]) -> dict[str, Any]:
    """Get metadata for the ontology."""
    version = kwargs_version(prefix, kwargs)
    path = prefix_cache_join(prefix, name="metadata.json", version=version)

    @cached_json(path=path, force=force_cache(kwargs))
    def _get_json() -> dict[str, Any]:
        ontology = get_ontology(prefix, **kwargs)
        return ontology.get_metadata()

    return cast(dict[str, Any], _get_json())
