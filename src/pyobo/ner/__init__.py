"""Wrapper around NER functionalities."""

from .api import get_grounder, ground, ground_best

__all__ = ["get_grounder", "ground", "ground_best"]
