from typing import Tuple

import bioregistry
from funowl import (
    Annotation,
    AnnotationAssertion,
    AnnotationProperty,
    Class,
    ObjectProperty,
    Ontology,
    OntologyDocument,
)
from rdflib import DCTERMS, OWL, RDFS, Literal, Namespace
from tqdm.auto import tqdm

from pyobo import Obo

__all__ = [
    "get_stuff",
]

IAO = Namespace("http://purl.obolibrary.org/obo/IAO_")
OMO = Namespace("http://purl.obolibrary.org/obo/OMO_")
RO = Namespace("http://purl.obolibrary.org/obo/RO_")
OIO = Namespace("http://www.geneontology.org/formats/oboInOwl#")


def get_stuff(self: Obo, *, extension: str = ".ofn") -> Tuple[Ontology, OntologyDocument]:
    namespaces = {
        bioregistry.get_preferred_prefix(prefix) or prefix: Namespace(uri_prefix)
        for prefix, uri_prefix in self.idspaces.items()
    }
    namespaces.update(IAO=IAO, RO=RO, OMO=OMO, oboInOwl=OIO)
    namespaces[self.ontology] = default = Namespace(f"https://bioregistry.io/{self.ontology}:")

    def _uri(ref):
        p = bioregistry.get_preferred_prefix(ref.prefix) or ref.prefix
        return namespaces[p][ref.identifier]

    ontology = Ontology(
        iri=self.get_iri_stub() + extension,
        version=self.get_version_iri_stub() + extension if self.data_version else None,
    )
    if self.data_version:
        ontology.annotations.append(Annotation(OWL.versionInfo, self.data_version))
    ontology.annotations.append(Annotation(DCTERMS.title, self.name))
    ontology.annotations.append(
        Annotation(DCTERMS.description, bioregistry.get_description(self.ontology))
    )
    ontology.annotations.append(Annotation(RDFS.seeAlso, f"https://bioregistry.io/{self.ontology}"))
    ontology.declarations(AnnotationProperty(IAO["0000700"]))
    ontology.declarations(AnnotationProperty(IAO["0000115"]))

    for root_term in self.root_terms or []:
        ontology.annotation(
            IAO["0000700"],
            _uri(root_term),
        )

    for typedef in self.typedefs:
        typedef_iri = _uri(typedef)
        ontology.declarations(ObjectProperty(typedef_iri))
        if typedef.name:
            ontology.annotations.append(
                AnnotationAssertion(
                    RDFS.label,
                    typedef_iri,
                    Literal(typedef.name),
                    # [Annotation(DCTERMS.source, wikidata)],
                )
            )
        if typedef.definition:
            ontology.annotations.append(
                AnnotationAssertion(
                    IAO["0000115"],  # definition
                    typedef_iri,
                    typedef.definition,
                )
            )

    for term in tqdm(self, desc="converting to FunOWL", unit_scale=True):
        ontology.declarations(Class(default[term.identifier]))
        for parent in term.parents:
            ontology.subClassOf(
                default[term.identifier],
                _uri(parent),
            )
        if term.definition:
            ontology.annotations.append(
                AnnotationAssertion(
                    IAO["0000115"],  # definition
                    default[term.identifier],
                    term.definition,
                )
            )
        for typedef, references in term.relationships.items():
            pred = _uri(typedef)
            for reference in references:
                ontology.annotations.append(
                    AnnotationAssertion(
                        pred,
                        default[term.identifier],
                        _uri(reference),
                    )
                )
        for xref in term.xrefs:
            ontology.annotations.append(
                AnnotationAssertion(
                    OIO["hasDbXref"],
                    default[term.identifier],
                    _uri(xref),
                )
            )
        for synonym in term.synonyms:
            pass  # TODO
        for prop in term.properties:
            pass  # TODO
        if term.name:
            ontology.annotations.append(
                AnnotationAssertion(
                    RDFS.label,
                    default[term.identifier],
                    Literal(term.name),
                    # [Annotation(DCTERMS.source, wikidata)],
                ),
            )

    doc = OntologyDocument(
        ontology=ontology,
        dcterms=DCTERMS,
        owl=OWL,
        **namespaces,
    )
    return ontology, doc
