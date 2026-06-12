"""Read SKOS from RDF."""

from pathlib import Path

import curies
import rdflib
from bioregistry import NormalizedNamableReference, NormalizedNamedReference
from bioregistry.schema import AnnotatedURL
from rdflib import DCTERMS, RDF, RDFS, SKOS, VANN, Graph, Node, URIRef
from tqdm import tqdm

from pyobo import Annotation
from pyobo.identifier_utils import get_converter
from pyobo.struct import Obo, Term, build_ontology
from pyobo.struct.vocabulary import has_source

__all__ = [
    "get_skos_from_rdflib",
    "read_skos",
]


def read_skos(
    path: str | Path,
    *,
    prefix: str | None = None,
    converter: curies.Converter | None = None,
    rdf_format: str | None = None,
) -> Obo:
    """Read a SKOS RDF file."""
    graph = rdflib.Graph()
    graph.parse(path, format=rdf_format or "ttl")
    return get_skos_from_rdflib(
        graph,
        prefix=prefix,
        converter=converter,
        source=path if isinstance(path, str) and path.startswith("http") else None,
    )


def get_skos_from_rdflib(
    graph: rdflib.Graph,
    *,
    prefix: str | None = None,
    converter: curies.Converter | None = None,
    broad_match_becomes_parent: bool = True,
    source: str | None = None,
) -> Obo:
    """Extract an ontology from a SKOS RDF graph.

    :param source: The URL to the SKOS document
    :returns: An ontology.
    """
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
        get_term(
            graph,
            concept,
            converter=converter,
            broad_match_becomes_parent=broad_match_becomes_parent,
        )
        for concept in tqdm(
            graph.subjects(RDF.type, SKOS.Concept),
            desc=f"[{prefix}] SKOS concepts to OWL",
            unit="term",
            unit_scale=True,
            leave=False,
        )
    ]

    if source is None:
        source = str(scheme)

    return build_ontology(
        prefix=prefix,
        terms=terms,
        root_terms=root_terms,
        idspaces={curie_prefix: str(uri_prefix) for curie_prefix, uri_prefix in graph.namespaces()},
        name=_get_scheme_object_literal(DCTERMS.title),
        description=_get_scheme_object_literal(DCTERMS.description)
        or _get_scheme_object_literal(RDFS.comment),
        properties=[Annotation.uri(has_source, source)],
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
DEFAULT_LANGUAGES = {"en", "en-US", None}


def get_term(
    graph: rdflib.Graph,
    node: URIRef,
    converter: curies.Converter,
    broad_match_becomes_parent: bool = True,
) -> Term:
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
            term.append_exact_match(
                converter.parse_uri(str(exact_match), strict=True).to_pydantic()
            )
    for broad_match in graph.objects(node, SKOS.broadMatch):
        if isinstance(broad_match, URIRef):
            obj = converter.parse_uri(str(broad_match), strict=True).to_pydantic()
            if broad_match_becomes_parent and obj.prefix == term.prefix:
                term.append_parent(obj)
            else:
                term.append_broad_match(obj)
    for narrow_match in graph.objects(node, SKOS.narrowMatch):
        if isinstance(narrow_match, URIRef):
            term.append_narrow_match(
                converter.parse_uri(str(narrow_match), strict=True).to_pydantic()
            )
    for related_match in graph.objects(node, SKOS.relatedMatch):
        if isinstance(related_match, URIRef):
            term.append_related_match(
                converter.parse_uri(str(related_match), strict=True).to_pydantic()
            )
    return term


def _demo() -> None:
    import bioregistry
    from tabulate import tabulate

    rows = []
    for resource in bioregistry.resources():
        match resource.get_download_skos(get_format=True):
            case None:
                continue
            case str() as url:
                try:
                    ontology = read_skos(url, prefix=resource.prefix)
                except SyntaxError:
                    tqdm.write(f"need explicit RDF format for {resource.prefix}")
                    continue
                ontology.write_obo(f"/Users/cthoyt/Desktop/{resource.prefix}.obo")
                rows.append((resource.prefix, url, "", len(list(ontology.iter_terms()))))
            case AnnotatedURL() as model:
                ontology = read_skos(model.url, prefix=resource.prefix, rdf_format=model.rdf_format)
                ontology.write_obo(f"/Users/cthoyt/Desktop/{resource.prefix}.obo")
                rows.append(
                    (resource.prefix, model.url, model.rdf_format, len(list(ontology.iter_terms())))
                )

    tqdm.write(tabulate(rows))


if __name__ == "__main__":
    _demo()
