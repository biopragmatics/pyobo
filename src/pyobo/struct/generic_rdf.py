"""Read from RDF."""

from pathlib import Path

import curies
import rdflib
from bioregistry import NormalizedNamedReference
from curies import ReferenceTuple
from rdflib import OWL, RDF, RDFS, SKOS, Graph, Node, URIRef
from tqdm import tqdm

from pyobo.identifier_utils import get_converter
from pyobo.struct import Obo, Term, TypeDef, build_ontology

__all__ = [
    "read_generic_rdf",
]


def read_generic_rdf(
    path: str | Path,
    *,
    prefix: str,
    converter: curies.Converter | None = None,
    rdf_format: str | None = None,
) -> Obo:
    """Read an RDF file."""
    graph = rdflib.Graph()
    graph.parse(path, format=rdf_format)
    return _get_ontology(graph, prefix=prefix, converter=converter)


TERM_OBJECT_TYPES: list[Node] = [RDFS.Class, SKOS.Concept, OWL.Class, OWL.NamedIndividual]
TYPEDEF_OBJECT_TYPES: list[Node] = [RDF.Property]


def _get_ontology(
    graph: rdflib.Graph,
    *,
    prefix: str,
    converter: curies.Converter | None = None,
) -> Obo:
    """Extract an ontology from a SKOS RDF graph."""
    if converter is None:
        converter = get_converter()
    terms = [
        term
        for concept in tqdm(graph.subjects(RDF.type, TERM_OBJECT_TYPES))
        if isinstance(concept, URIRef)
        and (term := get_term(graph, concept, converter=converter)) is not None
    ]
    typedefs = [
        typedef
        for concept in tqdm(graph.subjects(RDF.type, TYPEDEF_OBJECT_TYPES))
        if isinstance(concept, URIRef)
        and (typedef := get_typedef(graph, concept, converter=converter)) is not None
    ]
    return build_ontology(
        prefix=prefix,
        terms=terms,
        typedefs=typedefs,
        idspaces={curie_prefix: str(uri_prefix) for curie_prefix, uri_prefix in graph.namespaces()},
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


def get_term(graph: rdflib.Graph, node: URIRef, converter: curies.Converter) -> Term | None:
    """Get a term."""
    reference_tuple: ReferenceTuple | None = converter.parse_uri(str(node), strict=False)
    if reference_tuple is None:
        return None
    labels = _literal_objects(graph, node, RDFS.label) or _literal_objects(
        graph, node, SKOS.prefLabel
    )
    definitions = _literal_objects(graph, node, SKOS.definition)  # MULTIPLE
    # TODO decide if class or individual
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


def get_typedef(graph: rdflib.Graph, node: URIRef, converter: curies.Converter) -> TypeDef | None:
    """Get a typedef."""
    return None


def _demo():
    import pystow

    url = "https://nfdi4ing.pages.rwth-aachen.de/metadata4ing/metadata4ing/ontology.ttl"
    graph = pystow.ensure_rdf("dalia", url=url)
    ontology = _get_ontology(graph, prefix="m4i")
    ontology.write_obo("/Users/cthoyt/Desktop/m4i.obo")


if __name__ == "__main__":
    _demo()
