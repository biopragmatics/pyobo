"""Read JSKOS."""

import itertools as itt
from collections.abc import Iterable
from pathlib import Path

import curies
import jskos
from jskos import ProcessedConcept, ProcessedKOS

from pyobo.struct import Obo, build_ontology
from pyobo.identifier_utils import get_converter

__all__ = [
    "from_pkos",
    "read_jskos",
]


def read_jskos(path: str | Path, *, prefix: str, converter: curies.Converter | None = None) -> Obo:
    """Read JSKOS into an ontology."""
    if converter is None:
        converter = get_converter()
    pkos = jskos.read(path).process(converter)
    return from_pkos(prefix=prefix, pkos=pkos)


def from_pkos(prefix: str, pkos: ProcessedKOS) -> Obo:
    """Get from a processed knowledge organization system."""
    return build_ontology(
        prefix=prefix,
        terms=get_terms(pkos),
    )


def get_terms(pkos: ProcessedKOS) -> Iterable[ProcessedConcept]:
    return list(itt.chain.from_iterable(_iterate_concepts_inner(c) for c in pkos.concepts))


def _iterate_concepts_inner(concept: ProcessedConcept):
    yield concept
    for narrower in concept.narrower:
        yield from _iterate_concepts_inner(narrower)
    for broader in concept.broader:
        yield from _iterate_concepts_inner(broader)
    for _mapping in concept.mappings:
        raise NotImplementedError
