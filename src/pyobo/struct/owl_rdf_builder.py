import itertools as itt
from pathlib import Path
from typing import TYPE_CHECKING, Dict, List, Mapping, Optional, Protocol, Union

import bioregistry
import click
import typing_extensions
from rdflib import (
    DCTERMS,
    OWL,
    RDF,
    RDFS,
    SKOS,
    BNode,
    Graph,
    Literal,
    Namespace,
    URIRef,
)
from tqdm.auto import tqdm

if TYPE_CHECKING:
    import pyobo

HERE = Path(__file__).parent.resolve()
IAO = Namespace("http://purl.obolibrary.org/obo/IAO_")
OMO = Namespace("http://purl.obolibrary.org/obo/OMO_")
RO = Namespace("http://purl.obolibrary.org/obo/RO_")
OIO = Namespace("http://www.geneontology.org/formats/oboInOwl#")
DEBIO = Namespace("https://bioregistry.io/debio:")

ROOT_TERM = IAO["0000700"]
DESCRIPTION = IAO["0000115"]
HAS_DB_XREF = OIO["hasDbXref"]
SYNONYM_TYPE = OIO["hasSynonymType"]
SYNONYM_TYPE_PROPERTY = OIO["SynonymTypeProperty"]
HAS_SCOPE = OIO["hasScope"]


Specificity = typing_extensions.Literal["EXACT", "NARROW", "BROAD", "RELATED"]

SKOSMAP: Mapping[Specificity, URIRef] = {
    "EXACT": SKOS.exactMatch,
    "NARROW": SKOS.narrowMatch,
    "BROAD": SKOS.broadMatch,
    "RELATED": SKOS.relatedMatch,
}
SYNMAP: Mapping[Specificity, URIRef] = {
    "EXACT": OIO["hasExactSynonym"],
    "NARROW": OIO["hasNarrowSynonym"],
    "BROAD": OIO["hasBroadSynonym"],
    "RELATED": OIO["hasRelatedSynonym"],
}


class Referencable(Protocol):
    prefix: str
    identifier: str


class OWLRDF:
    def __init__(
        self,
        prefix: str,
        iri: str,
        prefix_map: Mapping[str, str],
        *,
        version_iri: Optional[str] = None,
        version: Optional[str] = None,
        root_terms: Optional[List[str]] = None,
        description: Optional[str] = None,
        name: Optional[str] = None,
        manager: Optional[bioregistry.Manager] = None,
    ):
        self.graph = Graph()
        self.br = manager or bioregistry.manager
        self.converter = self.br.get_converter()
        self.prefix = prefix
        self.namespace = Namespace(f"{self.br.base_url}/{self.prefix}:")

        namespaces = {
            self.br.get_preferred_prefix(prefix) or prefix: Namespace(uri_prefix)
            for prefix, uri_prefix in prefix_map.items()
        }
        namespaces.update(IAO=IAO, RO=RO, OMO=OMO, oboInOwl=OIO, DC=DCTERMS, DeBiO=DEBIO)
        namespaces[self.prefix] = self.namespace
        self.namespaces = namespaces
        for p, n in namespaces.items():
            self.graph.bind(p, n)

        self.iri = URIRef(iri)

        self.add_ontology(RDF.type, OWL.Ontology)
        if version_iri:
            self.add_ontology(OWL.versionIRI, URIRef(version_iri))
        if description:
            self.add_ontology(DCTERMS.description, Literal(description))
        if name:
            self.add_ontology(DCTERMS.title, Literal(name))
        if version:
            self.add_ontology(OWL.versionInfo, Literal(version))
        for root_term in root_terms or []:
            self.add_ontology(ROOT_TERM, self.reference(root_term))

        add_standard(self.graph)

    def reference(self, referencable: Referencable) -> URIRef:
        return self.pair(referencable.prefix, referencable.identifier)

    def pair(self, prefix: str, identifier: str) -> URIRef:
        preferred_prefix = self.br.get_preferred_prefix(prefix) or prefix
        return self.namespaces[preferred_prefix][identifier]

    def parse_safe(self, t: str):
        """omni parser for curie / URI / naked curie"""
        if not t:
            return None
        prefix, identifier = self.converter.parse_uri(t)
        if prefix and identifier:
            return self.pair(prefix, identifier)
        prefix, identifier = self.br.parse_curie(t)
        if prefix and identifier:
            return self.pair(prefix, identifier)
        if ":" in t:
            raise KeyError
        return self.pair(self.prefix, t)

    def add_ontology(self, p, o):
        self.add(self.iri, p, o)

    def add(self, s, p, o):
        self.graph.add((s, p, o))

    def add_label(self, s, label: str):
        self.add(s, RDFS.label, Literal(label))

    def add_description(self, s, description: str):
        self.add(s, DESCRIPTION, Literal(description))

    def add_type(self, s, o):
        self.add(s, RDF.type, o)

    def add_class(self, s):
        self.add_type(s, OWL.Class)

    def add_subclass(self, s, o):
        self.add(s, RDFS.subClassOf, o)

    def add_object_property(self, s):
        self.add_type(s, OWL.ObjectProperty)

    def add_subproperty(self, s, o):
        self.add(s, RDFS.subPropertyOf, o)

    def add_annotation_property(self, s):
        self.add_type(s, OWL.AnnotationProperty)

    def add_dbxref(self, s, o):
        self.add_class(o)
        self.add(s, HAS_DB_XREF, o)

    def add_synonym(
        self,
        s,
        specificity: Specificity,
        value: str,
        synonym_type: Union[None, URIRef, Referencable] = None,
        xrefs: Optional[List[Referencable]] = None,
    ):
        qualifiers = []
        qualifiers.extend((HAS_DB_XREF, self.reference(xref)) for xref in xrefs or [])
        if isinstance(synonym_type, URIRef):
            qualifiers.append((SYNONYM_TYPE, synonym_type))
        elif synonym_type is not None:
            qualifiers.append((SYNONYM_TYPE, self.reference(synonym_type)))
        predicate = SYNMAP[specificity]
        self.add_axiom(
            s,
            predicate,
            Literal(value),
            *qualifiers,
        )

    def add_axiom(self, s, p, o, *qualifiers):
        self.add(s, p, o)
        if not qualifiers:
            return
        bnode = BNode()
        self.add(bnode, RDF.type, OWL.Axiom)
        self.add(bnode, OWL.annotatedSource, s)
        self.add(bnode, OWL.annotatedProperty, p)
        self.add(bnode, OWL.annotatedTarget, o)
        for qualifier_p, qualifier_o in qualifiers:
            self.add(bnode, qualifier_p, qualifier_o)


def add_standard(g: Graph):
    for s, t, d in [
        (DESCRIPTION, OWL.AnnotationProperty, "definition"),
        (HAS_DB_XREF, OWL.AnnotationProperty, "database cross-reference"),
        (SYNMAP["EXACT"], OWL.AnnotationProperty, "has exact synonym"),
        (SYNMAP["BROAD"], OWL.AnnotationProperty, "has broad synonym"),
        (SYNMAP["NARROW"], OWL.AnnotationProperty, "has narrow synonym"),
        (SYNMAP["RELATED"], OWL.AnnotationProperty, "has related synonym"),
        (SYNONYM_TYPE, OWL.AnnotationProperty, "has synonym type"),
        (RDFS.comment, OWL.AnnotationProperty, "comment"),
        (RDFS.label, OWL.AnnotationProperty, "label"),
        (ROOT_TERM, OWL.AnnotationProperty, "root term"),
        (HAS_SCOPE, OWL.AnnotationProperty, "has scope"),
        (SYNONYM_TYPE_PROPERTY, OWL.AnnotationProperty, "synonym type property"),
    ]:
        g.add((s, RDF.type, t))
        g.add((s, RDFS.label, Literal(d)))


def from_obo(ontology: "pyobo.Obo") -> OWLRDF:
    ext = ".ttl"

    g = OWLRDF(
        prefix=ontology.ontology,
        iri=ontology.get_iri_stub() + ext,
        name=ontology.name,
        version=ontology.data_version,
        version_iri=ontology.get_version_iri_stub() + ext,
        root_terms=ontology.root_terms,
        prefix_map=ontology.idspaces,
    )
    g.add_ontology(RDFS.comment, Literal("Generated with PyOBO"))

    for typedef in ontology.typedefs:
        s = g.reference(typedef)
        g.add_object_property(s)
        if typedef.name:
            g.add_label(s, typedef.name)

    synonym_typedef_references: Dict[str, URIRef] = {}
    for synonym_typedef in ontology.synonym_typedefs or []:
        if not synonym_typedef.id:
            raise ValueError
        synonym_typedef_references[synonym_typedef.id] = ref = g.parse_safe(synonym_typedef.id)
        scope = SYNMAP[synonym_typedef.specificity or "EXACT"]
        g.add_annotation_property(ref)
        g.add_label(ref, synonym_typedef.name)
        g.add_subproperty(ref, SYNONYM_TYPE_PROPERTY)
        g.add(ref, OIO["hasScope"], scope)

    terms = list(itt.islice((term for term in ontology if term.synonyms), 200))
    for term in tqdm(terms, unit_scale=True, unit="term"):
        s = g.reference(term)
        g.add_class(s)
        if term.name:
            g.add_label(s, term.name)
        if term.definition:
            g.add_description(s, term.definition)
        for parent in term.parents:
            g.add_subclass(s, g.reference(parent))
        for relation, targets in term.relationships.items():
            p = g.reference(relation)
            for target in targets:
                target_ref = g.reference(target)
                g.add_class(target_ref)
                g.add(s, p, target_ref)
        for xref in term.xrefs:
            g.add_dbxref(s, g.reference(xref))
        for synonym in term.synonyms:
            g.add_synonym(
                s,
                specificity=synonym.specificity,
                value=synonym.name,
                synonym_type=synonym_typedef_references.get(synonym.type.id),
                xrefs=synonym.provenance,
            )
        for prop, values in term.properties.items():
            p = g.parse_safe(prop)
            for value in values:
                # todo typing of literals?
                g.add(s, p, Literal(value))

    return g


def main():
    from pyobo import get_ontology

    ontology = get_ontology("hgnc")
    g = from_obo(ontology)
    path = HERE / f"{ontology.ontology}.ttl"
    click.secho(f"Serializing to {path}", fg="cyan", bold=True)
    g.graph.serialize(path, format="ttl")


if __name__ == "__main__":
    main()
