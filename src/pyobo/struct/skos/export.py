"""Exports to SKOS."""

from pathlib import Path

import curies
import rdflib
from rdflib import RDF, SKOS

from pyobo.struct import Obo, Term, TypeDef

__all__ = [
    "to_skos",
    "write_skos",
]


def write_skos(
    obo: Obo,
    path: str | Path,
    *,
    converter: curies.Converter | None = None,
    format: str | None = None,
) -> None:
    """Write an ontology to a file as SKOS."""
    graph = to_skos(obo, converter=converter)
    graph.serialize(path, format=format or "ttl")


def to_skos(obo: Obo, converter: curies.Converter) -> rdflib.Graph:
    """Get the ontology as a SKOS in a RDFLib graph."""
    graph = rdflib.Graph()
    node = rdflib.BNode()
    graph.add((node, RDF.type, SKOS.ConceptScheme))
    {typedef.reference: _typedef_to_skos(graph, typedef) for typedef in obo.typedefs or []}
    {term.reference: _term_to_skos(graph, term) for term in obo}
    return graph


def _typedef_to_skos(graph: rdflib.Graph, term: TypeDef) -> rdflib.Node:
    pass


def _term_to_skos(graph: rdflib.Graph, term: Term) -> rdflib.Node:
    pass
