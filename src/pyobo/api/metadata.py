"""High-level API for metadata."""

import logging
from collections.abc import Mapping

from .utils import get_version
from ..getters import get_ontology
from ..identifier_utils import wrap_norm_prefix
from ..utils.cache import cached_json
from ..utils.path import prefix_cache_join

__all__ = [
    "get_metadata",
]

logger = logging.getLogger(__name__)


@wrap_norm_prefix
def get_metadata(
    prefix: str,
    *,
    force: bool = False,
    version: str | None = None,
    force_process: bool = False,
    strict: bool = True,
) -> Mapping[str, str]:
    """Get metadata for the ontology."""
    if version is None:
        version = get_version(prefix)
    if force is None or force_process is None:
        raise TypeError
    path = prefix_cache_join(prefix, name="metadata.json", version=version)

    @cached_json(path=path, force=force or force_process)
    def _get_json() -> Mapping[str, str]:
        if force:
            logger.debug("[%s] forcing reload for metadata", prefix)
        else:
            logger.debug("[%s] no cached metadata found. getting from OBO loader", prefix)
        ontology = get_ontology(
            prefix, force=force, version=version, rewrite=force_process, strict=strict
        )
        return ontology.get_metadata()

    return _get_json()
