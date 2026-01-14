"""Wrapper around NER functionalities."""

from .api import get_grounder
from .normalizer import ground
from .scispacy_utils import (
    get_scispacy_entities,
    get_scispacy_entity_linker,
    get_scispacy_knowledgebase,
)

__all__ = [
    "get_grounder",
    "get_scispacy_entities",
    "get_scispacy_entity_linker",
    "get_scispacy_knowledgebase",
    "ground",
]
