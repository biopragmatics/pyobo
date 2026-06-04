"""Exports to SKOS."""

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


def _add_ontology_metadata(obo: Obo, graph: Graph, ontology_node: Node) -> None:
    import rdflib
    from rdflib import DCTERMS

    if obo.name:
        graph.add((ontology_node, DCTERMS.title, rdflib.Literal(obo.name)))


def to_skos(obo: Obo, *, converter: Converter | None = None, iri_: str | None = None) -> Graph:
    """Get the ontology as a SKOS in a RDFLib graph."""
    import itertools as itt

    import rdflib
    from rdflib import RDF, SKOS

    from ..struct import get_iris
    from ..typedef import INVERSES

    if converter is None:
        import bioregistry

        converter = bioregistry.get_default_converter()

    iri_, _ = get_iris(obo, extension=".ttl", iri=iri_)
    concept_scheme_node = rdflib.URIRef(iri_)

    graph = rdflib.Graph()
    converter.bind_rdflib(graph)
    graph.add((concept_scheme_node, RDF.type, SKOS.ConceptScheme))
    _add_ontology_metadata(obo, graph, concept_scheme_node)

    for root_term in obo.root_terms or []:
        root_node = _expand_rdflib(converter, root_term)
        graph.add((concept_scheme_node, SKOS.hasTopConcept, root_node))
        graph.add((root_node, SKOS.topConceptOf, concept_scheme_node))
        graph.add((root_node, RDF.type, SKOS.Concept))

    hierarchical_predicates = obo.get_hierarchical_predicates() or []
    inverse_hierarchical_predicates = [
        predicate_inverse
        for predicate in hierarchical_predicates
        if (predicate_inverse := INVERSES.get(predicate))
    ]

    for term in obo:
        term_node = _expand_rdflib(converter, term.reference)
        graph.add((term_node, RDF.type, SKOS.Concept))
        graph.add((term_node, SKOS.inScheme, concept_scheme_node))

        if term.name:
            graph.add((term_node, SKOS.prefLabel, rdflib.Literal(term.name)))
        if term.definition:
            graph.add((term_node, SKOS.definition, rdflib.Literal(term.definition)))

        for synonym in term.synonyms or []:
            graph.add(
                (term_node, SKOS.altLabel, rdflib.Literal(synonym.name, lang=synonym.language))
            )

        # Add all normal parents (i.e., is_a relations)
        for parent in term.parents or []:
            parent_node = _expand_rdflib(converter, parent)
            graph.add((term_node, SKOS.broadMatch, parent_node))
            graph.add((parent_node, SKOS.narrowMatch, term_node))
            if parent.prefix == obo.ontology:
                graph.add((parent_node, SKOS.inScheme, concept_scheme_node))

        # Add any non-standard parents (i.e., annotated with OMO:0003014,
        # see https://github.com/information-artifact-ontology/ontology-metadata/pull/193)
        for predicate in hierarchical_predicates or []:
            for predicate_parent in itt.chain(
                term.get_relationships(predicate),
                term.get_property_objects(predicate),
            ):
                predicate_parent_node = _expand_rdflib(converter, predicate_parent)
                graph.add((term_node, SKOS.broadMatch, predicate_parent_node))
                graph.add((predicate_parent_node, SKOS.narrowMatch, term_node))
                graph.add((predicate_parent_node, RDF.type, SKOS.Concept))
                if predicate_parent.prefix == obo.ontology:
                    graph.add((predicate_parent_node, SKOS.inScheme, concept_scheme_node))

        for predicate_inverse in inverse_hierarchical_predicates:
            for predicate_child in itt.chain(
                term.get_relationships(predicate_inverse),
                term.get_property_objects(predicate_inverse),
            ):
                predicate_child_node = _expand_rdflib(converter, predicate_child)
                graph.add((term_node, SKOS.narrowMatch, predicate_child_node))
                graph.add((predicate_child_node, SKOS.broadMatch, term_node))
                graph.add((predicate_child_node, RDF.type, SKOS.Concept))
                if predicate_child.prefix == obo.ontology:
                    graph.add((predicate_child_node, SKOS.inScheme, concept_scheme_node))

    return graph
