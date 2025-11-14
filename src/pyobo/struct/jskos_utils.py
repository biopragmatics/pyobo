"""Read JSKOS."""

from pathlib import Path

import curies

from .struct import Obo, build_ontology

__all__ = [
    "read_jskos",
]


def read_jskos(path: str | Path, *, prefix: str, converter: curies.Converter | None = None) -> Obo:
    """Read JSKOS into an ontology."""
    return build_ontology(prefix=prefix)
