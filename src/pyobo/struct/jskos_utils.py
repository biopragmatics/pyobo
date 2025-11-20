"""Read JSKOS."""

from pathlib import Path

import curies

from .struct import Obo, build_ontology
import jskos
from jskos import ProcessedConcept, ProcessedKOS

__all__ = [
    "read_jskos",
    "from_pkos",
]


def read_jskos(path: str | Path, *, prefix: str, converter: curies.Converter | None = None) -> Obo:
    """Read JSKOS into an ontology."""
    if converter is None:
        from ..identifier_utils import get_converter
        converter = get_converter()
    kos = jskos.read(path)
    pkos = jskos.process(kos, converter)
    return from_pkos(prefix=prefix, pkos=pkos)


def from_pkos(prefix: str, pkos: ProcessedKOS) -> Obo:
    raise NotImplementedError
    return build_ontology(prefix=prefix)


def _iterate_concepts(pkos: ProcessedKOS) -> list[ProcessedConcept]:
    for c in pkos.concepts:
        yield from _iterate_concepts_inner(c)


def _iterate_concepts_inner(concept: ProcessedConcept):
    yield concept
    for narrower in concept.narrower:
        yield from _iterate_concepts_inner(concept)
