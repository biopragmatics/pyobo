"""Read SKOS from RDF."""

from pathlib import Path

import curies
import rdflib
from bioregistry import NormalizedNamableReference, NormalizedNamedReference
from rdflib import DCTERMS, RDF, SKOS, VANN, Graph, Node, URIRef
from tqdm import tqdm

from pyobo.identifier_utils import get_converter
from pyobo.struct import Obo, Term, build_ontology

__all__ = [
    "get_skos_ontology",
    "read_skos",
]


def read_skos(
    path: str | Path, *, prefix: str | None = None, converter: curies.Converter | None = None
) -> Obo:
    """Read a SKOS RDF file."""
    graph = rdflib.Graph()
    graph.parse(path)
    return get_skos_ontology(graph, prefix=prefix, converter=converter)


def get_skos_ontology(
    graph: rdflib.Graph,
    *,
    prefix: str | None = None,
    converter: curies.Converter | None = None,
) -> Obo:
    """Extract an ontology from a SKOS RDF graph."""
    if converter is None:
        converter = get_converter()
    schemes = list(graph.subjects(RDF.type, SKOS.ConceptScheme))
    if len(schemes) != 1:
        raise ValueError
    scheme = schemes[0]

    def _get_scheme_object_literal(p: Node) -> str | None:
        for o in graph.objects(scheme, p):
            return str(o)
        return None

    if prefix is None:
        prefix = _get_scheme_object_literal(VANN.preferredNamespacePrefix)

    if prefix is None:
        raise ValueError(f"no prefix given nor found using {VANN.preferredNamespacePrefix}")

    root_terms = [
        NormalizedNamableReference.from_reference(converter.parse_uri(subject, strict=True))
        for subject in graph.objects(scheme, SKOS.hasTopConcept)
    ]
    terms = [
        get_term(graph, concept, converter=converter)
        for concept in tqdm(graph.subjects(RDF.type, SKOS.Concept))
    ]

    return build_ontology(
        prefix=prefix,
        terms=terms,
        root_terms=root_terms,
        idspaces={curie_prefix: str(uri_prefix) for curie_prefix, uri_prefix in graph.namespaces()},
        name=_get_scheme_object_literal(DCTERMS.title),
        description=_get_scheme_object_literal(DCTERMS.description),
    )


def _literal_objects(graph: Graph, subject: Node, predicate: Node) -> list[rdflib.Literal]:
    return [
        o
        for o in graph.objects(subject, predicate)
        if isinstance(o, rdflib.Literal) and o._language in DEFAULT_LANGUAGES
    ]


DEFAULT_LANGUAGES = {"en", None}


def get_term(graph: rdflib.Graph, node: URIRef, converter: curies.Converter) -> Term:
    """Get a term."""
    reference_tuple = converter.parse_uri(node, strict=True)
    labels = _literal_objects(graph, node, SKOS.prefLabel)
    definitions = _literal_objects(graph, node, SKOS.definition)
    term = Term(
        reference=NormalizedNamedReference(
            prefix=reference_tuple.prefix,
            identifier=reference_tuple.identifier,
            name=labels[0] if labels else None,
        ),
        definition=definitions[0] if definitions else None,
    )
    for alt in _literal_objects(graph, node, SKOS.altLabel):
        term.append_synonym(alt)

    for exact_match in graph.objects(node, SKOS.exactMatch):
        term.append_exact_match(converter.parse_uri(exact_match, strict=True))

    # TODO broad, narrow, related match. add to term functions too
    return term


def _split_literals(literals: list[rdflib.Literal]) -> tuple[str, str]:
    for literal in literals:
        if literal._language == "en" or literal._language is None:
            return literal, "en", {}
    literal = literals[0]
    return str(literal), literal._language, {}


def _demo():
    import pystow

    url = "https://raw.githubusercontent.com/dini-ag-kim/hcrt/refs/heads/master/hcrt.ttl"
    graph = pystow.ensure_rdf("dalia", url=url)
    ontology = get_skos_ontology(graph)
    ontology.write_obo("/Users/cthoyt/Desktop/hcrt.obo")


if __name__ == "__main__":
    _demo()
