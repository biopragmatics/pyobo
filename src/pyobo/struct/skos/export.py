"""Exports to SKOS.

See:

- https://www.w3.org/2006/07/SWD/SKOS/skos-and-owl/master.html#Transform1
"""

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from curies import Converter, Reference
    from rdflib import Graph, Node, URIRef

    from pyobo.struct import Obo, Term

__all__ = [
    "to_skos",
    "write_skos",
]


def write_skos(
    obo: Obo,
    path: str | Path,
    *,
    converter: Converter | None = None,
    format: str | None = None,
) -> None:
    """Write an ontology to a file as SKOS."""
    graph = to_skos(obo, converter=converter)
    graph.serialize(path, format=format or "ttl")


def _expand_rdflib(converter: Converter, reference: Reference) -> URIRef:
    import rdflib

    return rdflib.URIRef(converter.expand_reference(reference, strict=True))


def to_skos(obo: Obo, converter: Converter, concept_scheme_node: Node | None = None) -> Graph:
    """Get the ontology as a SKOS in a RDFLib graph."""
    import rdflib
    from rdflib import DCTERMS, RDF, SKOS

    graph = rdflib.Graph()
    if concept_scheme_node is None:
        concept_scheme_node = rdflib.BNode()
    graph.add((concept_scheme_node, RDF.type, SKOS.ConceptScheme))
    if obo.name:
        graph.add((concept_scheme_node, DCTERMS.title, rdflib.Literal(obo.name)))

    for root_term in obo.root_terms or []:
        root_node = _expand_rdflib(converter, root_term)
        graph.add((concept_scheme_node, SKOS.hasTopConcept, root_node))
        graph.add((root_node, SKOS.topConceptOf, concept_scheme_node))
        graph.add((root_node, RDF.type, SKOS.Concept))

    for term in obo:
        _term_to_skos(converter=converter, graph=graph, scheme=concept_scheme_node, term=term)

    return graph


def _term_to_skos(converter: Converter, graph: Graph, scheme: Node, term: Term) -> URIRef:
    import rdflib
    from rdflib import RDF, SKOS

    node = _expand_rdflib(converter, term.reference)
    graph.add((node, RDF.type, SKOS.Concept))
    graph.add((node, SKOS.prefLabel, rdflib.Literal(term.name)))
    for synonym in term.synonyms or []:
        graph.add((node, SKOS.altLabel, rdflib.Literal(synonym.name, lang=synonym.language)))
    for parent in term.parents or []:
        parent_node = _expand_rdflib(converter, parent)
        graph.add((node, SKOS.broadMatch, parent_node))
        graph.add((parent_node, SKOS.narrowMatch, node))
        graph.add((node, SKOS.inScheme, scheme))
    if term.definition:
        graph.add((node, SKOS.scopeNote, rdflib.Literal(term.definition)))
    return node
