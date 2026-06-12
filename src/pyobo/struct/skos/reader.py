"""Read SKOS from RDF."""

import itertools as itt
from collections.abc import Iterable
from pathlib import Path

import curies
import rdflib
from bioregistry import NormalizedNamableReference, NormalizedNamedReference
from bioregistry.schema import AnnotatedURL
from curies import Reference
from curies import vocabulary as v
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
    terms: dict[Reference, Term] = {}
    for concept in tqdm(
        graph.subjects(RDF.type, SKOS.Concept),
        desc=f"[{prefix}] SKOS concepts to OWL",
        unit="term",
        unit_scale=True,
        leave=False,
    ):
        term = get_term(
            graph,
            concept,
            converter=converter,
            broad_match_becomes_parent=broad_match_becomes_parent,
        )
        terms[term.reference] = term

    _cleanup_narrow_matches(terms)

    if source is None:
        source = str(scheme)

    # if SKOS-XL, like in tib.mbv, there might
    # be multiple terms, one for each synonym.
    # maybe map them as "alternate terms"? if there
    # are multiple exact matches in the same ontology,
    # and one but not the others has parents, then
    # that one becomes the main term. otherwise, it's
    # not clear how to do this

    prefixes_used = {"dcterms", "rdfs", "iao"}
    for term in terms.values():
        prefixes_used.update(term._get_prefixes())

    prefix_map = {
        curie_prefix: str(uri_prefix)
        for curie_prefix, uri_prefix in graph.namespaces()
        if curie_prefix in prefixes_used
    }

    return build_ontology(
        prefix=prefix,
        terms=list(terms.values()),
        root_terms=root_terms,
        idspaces=prefix_map,
        name=_get_scheme_object_literal(DCTERMS.title),
        description=_get_scheme_object_literal(DCTERMS.description)
        or _get_scheme_object_literal(RDFS.comment),
        properties=[Annotation.uri(has_source, source)],
    )


def _cleanup_narrow_matches(terms: dict[Reference, Term]) -> None:
    for parent in terms.values():
        for child in parent.get_property_objects(v.narrow_match):
            if isinstance(child, Reference) and child in terms and parent in terms[child].parents:
                parent.remove_property_object(v.narrow_match, child)


def _literal_objects(
    graph: Graph, subject: Node, predicate: Node, language_priority: dict[str | None, int]
) -> list[rdflib.Literal]:
    language_literal_pairs: Iterable[tuple[str | None, rdflib.Literal]] = (
        (literal._language, literal)
        for literal in graph.objects(subject, predicate)
        if isinstance(literal, rdflib.Literal) and literal._language in DEFAULT_LANGUAGES
    )
    langauge_literal_pairs = sorted(
        language_literal_pairs, key=lambda lang_value: language_priority.get(lang_value[0], 1_000)
    )
    return [literal for _language, literal in langauge_literal_pairs]


# until we have a better way of representing internationalization, this
# just extracts a language-less or english language literal. otherwise,
# it takes one at random
DEFAULT_LANGUAGES = ["en", "en-US", None, "de"]
DEFAULT_LANGUAGE_PRIORITY = {lang: i for i, lang in enumerate(DEFAULT_LANGUAGES)}


def get_term(
    graph: rdflib.Graph,
    node: URIRef,
    converter: curies.Converter,
    broad_match_becomes_parent: bool = True,
) -> Term:
    """Get a term."""
    language_priority = DEFAULT_LANGUAGE_PRIORITY

    reference_tuple = converter.parse_uri(str(node), strict=True)
    labels = _literal_objects(graph, node, SKOS.prefLabel, language_priority)
    definitions = _literal_objects(graph, node, SKOS.definition, language_priority)
    term = Term(
        reference=NormalizedNamedReference(
            prefix=reference_tuple.prefix,
            identifier=reference_tuple.identifier,
            name=labels[0] if labels else None,
        ),
        definition=definitions[0] if definitions else None,
    )
    for alt in _literal_objects(graph, node, SKOS.altLabel, language_priority):
        if alt._language in language_priority:
            term.append_synonym(alt, language=alt._language)

    for exact_match in graph.objects(node, SKOS.exactMatch):
        if isinstance(exact_match, URIRef):
            term.append_exact_match(
                converter.parse_uri(str(exact_match), strict=True).to_pydantic()
            )
    for broad_match in itt.chain(
        graph.objects(node, SKOS.broader),
        graph.objects(node, SKOS.broadMatch),
    ):
        if isinstance(broad_match, URIRef):
            obj = converter.parse_uri(str(broad_match), strict=True).to_pydantic()
            if broad_match_becomes_parent and obj.prefix == term.prefix:
                term.append_parent(obj)
            else:
                term.append_broad_match(obj)
    for narrow_match in itt.chain(
        graph.objects(node, SKOS.narrower),
        graph.objects(node, SKOS.narrowMatch),
    ):
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

    # for resource in bioregistry.resources():
    #     rdf = resource.get_download_rdf(get_format=True)
    #     if rdf and not resource.get_download_skos():
    #         print(resource.prefix, rdf)
    # return

    for resource in tqdm(bioregistry.resources()):
        match resource.get_download_skos(get_format=True):
            case None:
                continue
            case str() as url:
                try:
                    ontology = read_skos(url, prefix=resource.prefix)
                except SyntaxError:
                    tqdm.write(f"need explicit RDF format for {resource.prefix}")
                    continue
                rows.append((resource.prefix, url, "", *_summarize(ontology)))
            case AnnotatedURL() as model:
                ontology = read_skos(model.url, prefix=resource.prefix, rdf_format=model.rdf_format)
                rows.append((resource.prefix, model.url, model.rdf_format, *_summarize(ontology)))
        ontology.write_obo(f"/Users/cthoyt/Desktop/{resource.prefix}.obo")

    tqdm.write(tabulate(rows, headers=["prefix", "url", "format", "terms", "parents"]))


def _summarize(ontology: Obo) -> tuple[int, ...]:
    n_parents = 0
    n_terms = 0
    for term in ontology:
        n_terms += 1
        n_parents += len(term.parents)
    return n_terms, n_parents


if __name__ == "__main__":
    _demo()
