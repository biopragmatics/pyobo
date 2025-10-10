"""Read SKOS from RDF."""

from pathlib import Path

import curies
import rdflib
from bioregistry import NormalizedNamableReference, NormalizedNamedReference
from rdflib import DCTERMS, RDF, RDFS, SKOS, VANN, Graph, Node, URIRef
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
        NormalizedNamableReference.from_reference(
            converter.parse_uri(str(subject), strict=True).to_pydantic()
        )
        for subject in graph.objects(scheme, SKOS.hasTopConcept)
    ]
    terms = [
        get_term(graph, concept, converter=converter)
        for concept in tqdm(graph.subjects(RDF.type, SKOS.Concept))
    ]

    # FIXME need to put in parents

    return build_ontology(
        prefix=prefix,
        terms=terms,
        root_terms=root_terms,
        idspaces={curie_prefix: str(uri_prefix) for curie_prefix, uri_prefix in graph.namespaces()},
        name=_get_scheme_object_literal(DCTERMS.title),
        description=_get_scheme_object_literal(DCTERMS.description)
        or _get_scheme_object_literal(RDFS.comment),
    )


def _literal_objects(graph: Graph, subject: Node, predicate: Node) -> list[rdflib.Literal]:
    return [
        o
        for o in graph.objects(subject, predicate)
        if isinstance(o, rdflib.Literal) and o._language in DEFAULT_LANGUAGES
    ]


# until we have a better way of representing internationalization, this
# just extracts a language-less or english language literal. otherwise,
# it takes one at random
DEFAULT_LANGUAGES = {"en", None}


def get_term(graph: rdflib.Graph, node: URIRef, converter: curies.Converter) -> Term:
    """Get a term."""
    reference_tuple = converter.parse_uri(str(node), strict=True)
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
        if isinstance(exact_match, URIRef):
            term.append_exact_match(converter.parse_uri(str(exact_match), strict=True))
    for broad_match in graph.objects(node, SKOS.broadMatch):
        if isinstance(broad_match, URIRef):
            term.append_broad_match(converter.parse_uri(str(broad_match), strict=True))
    for narrow_match in graph.objects(node, SKOS.narrowMatch):
        if isinstance(narrow_match, URIRef):
            term.append_narrow_match(converter.parse_uri(str(narrow_match), strict=True))
    for related_match in graph.objects(node, SKOS.relatedMatch):
        if isinstance(related_match, URIRef):
            term.append_related_match(converter.parse_uri(str(related_match), strict=True))
    return term


def _demo():
    import pystow

    url = "https://raw.githubusercontent.com/dini-ag-kim/hcrt/refs/heads/master/hcrt.ttl"
    graph = pystow.ensure_rdf("dalia", url=url)
    ontology = get_skos_ontology(graph)
    ontology.write_obo("/Users/cthoyt/Desktop/hcrt.obo")


if __name__ == "__main__":
    _demo()
