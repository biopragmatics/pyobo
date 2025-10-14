"""Read JSKOS."""

from pathlib import Path

import curies
import jskos

from .struct import Obo

__all__ = [
    "read_jskos",
]


def read_jskos(
    path: str | Path, *, prefix: str | None = None, converter: curies.Converter | None = None
) -> Obo:
    """Read JSKOS into an ontology."""
    path = jskos.read(path)
    raise NotImplementedError
