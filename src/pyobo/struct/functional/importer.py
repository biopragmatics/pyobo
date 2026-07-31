"""Import OBO from OFN."""

from __future__ import annotations

import curies
import rdflib
from curies import Converter
from functional_owl import Document
from functional_owl import dsl as f

from ..struct import Obo, Term, TypeDef, build_ontology, default_reference
from ...identifier_utils import Reference


def ontology_from_document(prefix: str, document: Document) -> Obo:
    """Get an ontology from a functional OWL document."""
    if len(document.ontologies) != 1:
        raise ValueError

    ontology = document.ontologies[0]
    terms = {}
    typedefs = {}
    synonym_typedefs = {}
    kwargs = {}

    converter = Converter.from_prefix_map(document.prefix_map)
    ss = f"http://purl.obolibrary.org/obo/{prefix}#"

    # Pass 1: get declarations
    for declaration in ontology.axioms:
        if not isinstance(declaration, f.Declaration):
            continue

        match declaration.node.identifier:
            case curies.Reference():
                uri = converter.expand_reference(declaration.node.identifier, strict=True)
                if str(uri) == ss:
                    continue
                elif uri.startswith(ss):
                    reference = default_reference(prefix, uri.removeprefix(ss))
                else:
                    reference = Reference.from_reference(converter.parse_uri(uri, strict=True))
            case rdflib.URIRef():
                reference = Reference.from_reference(
                    converter.parse_uri(str(declaration.node.identifier), strict=True)
                )
            case _:
                raise TypeError

        match declaration.type:
            case "Class":
                terms[reference] = Term(reference=reference, type="Term")
            case "NamedIndividual":
                terms[reference] = Term(reference=reference, type="Instance")
            case "ObjectProperty":
                typedefs[reference] = TypeDef(reference=reference, predicate_type="object")
            case "DataProperty":
                typedefs[reference] = TypeDef(reference=reference, predicate_type="data")
            case "AnnotationProperty":
                typedefs[reference] = TypeDef(reference=reference, predicate_type="annotation")
            case "Datatype":
                raise NotImplementedError
            case _:
                raise ValueError(f"invalid declaration type: {declaration.type}")

    # Pass 2: fill up everything

    return build_ontology(
        prefix,
        idspaces=document.prefix_map,
        terms=list(terms.values()),
        typedefs=list(typedefs.values()),
        synonym_typedefs=list(synonym_typedefs.values()),
        ontology_iri=ontology.iri,
        ontology_version_iri=ontology.version_iri,
        **kwargs,
    )
