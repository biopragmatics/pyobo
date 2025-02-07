"""Wrapper around NER functionalities."""

from .api import get_grounder, ground, ground_best, literal_mappings_to_gilda

__all__ = [
    "get_grounder",
    "ground",
    "ground_best",
    "literal_mappings_to_gilda",
]
