"""Import OBO from OFN."""

from __future__ import annotations

from typing import Any

import curies
import rdflib
from curies import Converter
from functional_owl import Document
from functional_owl import dsl as f

from ..reference import default_reference
from ..struct import Obo, SynonymTypeDef, Term, TypeDef, build_ontology
from ...identifier_utils import Reference


def get_obo_from_ofn(prefix: str, document: Document) -> Obo:
    """Get an ontology from a functional OWL document."""
    if len(document.ontologies) != 1:
        raise ValueError

    ontology = document.ontologies[0]
    terms = {}
    typedefs = {}
    synonym_typedefs: dict[str, SynonymTypeDef] = {}
    kwargs: dict[str, Any] = {}

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
