"""Wrapper around NER functionalities."""

from .api import get_grounder
from .normalizer import ground

__all__ = [
    "get_grounder",
    "ground",
]
