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
    kos = jskos.read(path)
    raise NotImplementedError(
        f"not implemented for KOS with {len(kos.has_top_concept)} top concepts"
    )
