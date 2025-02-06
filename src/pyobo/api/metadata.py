"""High-level API for metadata."""

import logging
from collections import Counter
from functools import lru_cache
from typing import Any, cast

from typing_extensions import Unpack

from .utils import get_version_from_kwargs
from ..constants import GetOntologyKwargs, check_should_force
from ..getters import get_ontology
from ..identifier_utils import wrap_norm_prefix
from ..utils.cache import cached_json
from ..utils.path import prefix_cache_join

__all__ = [
    "get_metadata",
    "get_prefixes",
    "get_references_to",
]

logger = logging.getLogger(__name__)


@lru_cache
@wrap_norm_prefix
def get_metadata(prefix: str, **kwargs: Unpack[GetOntologyKwargs]) -> dict[str, Any]:
    """Get metadata for the ontology."""
    version = get_version_from_kwargs(prefix, kwargs)
    path = prefix_cache_join(prefix, name="metadata.json", version=version)

    @cached_json(path=path, force=check_should_force(kwargs))
    def _get_json() -> dict[str, Any]:
        ontology = get_ontology(prefix, **kwargs)
        return ontology.get_metadata()

    return cast(dict[str, Any], _get_json())


def get_prefixes(prefix: str, **kwargs: Unpack[GetOntologyKwargs]) -> Counter[str]:
    """Count the number of unique references to each vocabulary appear in the ontology."""
    ontology = get_ontology(prefix, **kwargs)
    return Counter({k: len(values) for k, values in ontology._get_references().items()})


def get_references_to(prefix: str, ext: str, **kwargs: Unpack[GetOntologyKwargs]) -> dict[str, int]:
    """Count the number of unique references to each vocabulary appear in the ontology."""
    ontology = get_ontology(prefix, **kwargs)
    references = ontology._get_references().get(ext, set())
    # TODO get specific references? this makes the data model one level more complicated
    return {r.identifier: 1 for r in references}
