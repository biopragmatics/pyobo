"""Exports to SKOS.

See:

- https://www.w3.org/2006/07/SWD/SKOS/skos-and-owl/master.html#Transform1
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from curies import Converter, Reference
    from rdflib import Graph, Node, URIRef

    from pyobo.struct import Obo

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


def to_skos(
    obo: Obo, *, converter: Converter | None = None, concept_scheme_node: str | Node | None = None
) -> Graph:
    """Get the ontology as a SKOS in a RDFLib graph."""
    import rdflib
    from rdflib import DCTERMS, RDF, SKOS

    if converter is None:
        import bioregistry

        converter = bioregistry.get_default_converter()

    if concept_scheme_node is None:
        concept_scheme_node = rdflib.BNode()
    elif isinstance(concept_scheme_node, Node):
        pass  # this needs to come before checking str
    elif isinstance(concept_scheme_node, str):
        concept_scheme_node = rdflib.URIRef(concept_scheme_node)

    graph = rdflib.Graph()
    graph.add((concept_scheme_node, RDF.type, SKOS.ConceptScheme))
    if obo.name:
        graph.add((concept_scheme_node, DCTERMS.title, rdflib.Literal(obo.name)))

    for root_term in obo.root_terms or []:
        root_node = _expand_rdflib(converter, root_term)
        graph.add((concept_scheme_node, SKOS.hasTopConcept, root_node))
        graph.add((root_node, SKOS.topConceptOf, concept_scheme_node))
        graph.add((root_node, RDF.type, SKOS.Concept))

    hierarchical_predicates = obo.get_hierarchical_predicates() or []

    for term in obo:
        term_node = _expand_rdflib(converter, term.reference)
        graph.add((term_node, RDF.type, SKOS.Concept))
        graph.add((term_node, SKOS.prefLabel, rdflib.Literal(term.name)))
        for synonym in term.synonyms or []:
            graph.add(
                (term_node, SKOS.altLabel, rdflib.Literal(synonym.name, lang=synonym.language))
            )

        # Add all normal parents (i.e., is_a relations)
        for parent in term.parents or []:
            parent_node = _expand_rdflib(converter, parent)
            graph.add((term_node, SKOS.broadMatch, parent_node))
            graph.add((parent_node, SKOS.narrowMatch, term_node))
            graph.add((parent_node, SKOS.inScheme, concept_scheme_node))

        # Add any non-standard parents (i.e., annotated with OMO:0003014,
        # see https://github.com/information-artifact-ontology/ontology-metadata/pull/193)
        for predicate in hierarchical_predicates or []:
            for v in term.get_relationships(predicate):
                object_parent_node = _expand_rdflib(converter, v)
                graph.add((term_node, SKOS.broadMatch, object_parent_node))
                graph.add((object_parent_node, SKOS.narrowMatch, term_node))
                graph.add((object_parent_node, SKOS.inScheme, concept_scheme_node))

        if term.definition:
            graph.add((term_node, SKOS.scopeNote, rdflib.Literal(term.definition)))

    return graph
