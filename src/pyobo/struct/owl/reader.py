"""Read OWL/XML."""

from __future__ import annotations

import typing
from collections import defaultdict
from collections.abc import Iterable
from pathlib import Path

import functional_owl as f
import rdflib
from curies import Converter, Reference
from functional_owl import (
    Annotation,
    AnnotationAssertion,
    Declaration,
    DeclarationType,
    Document,
    Ontology,
    Prefix,
)
from lxml import etree
from lxml.etree import Element
from pystow.utils import safe_open
from rdflib import XSD

from pyobo import Obo
from pyobo.struct.functional import ontology_from_document

__all__ = [
    "get_ofn_document",
    "read_owl",
]

OWL_PREFIX = "http://www.w3.org/2002/07/owl#"


def _owl(owl_luid: str) -> str:
    return "{http://www.w3.org/2002/07/owl#}" + owl_luid


OWL_CLASS_TAG = _owl("Class")
OWL_ANNOTATION_PROPERTY_TAG = _owl("Class")


def read_owl(prefix: str, path: str | Path) -> Obo:
    """Read OWL from a file."""
    document = get_ofn_document(prefix, path)
    return ontology_from_document(prefix, document)


def get_ofn_document(prefix: str, path: str | Path) -> Document:
    """Read OWL/XML into the functional OWL data model."""
    with safe_open(path) as file:
        tree = etree.parse(file)

    axioms: list[f.Box] = []
    _ola: list[f.Annotation] = []
    prefixes: list[f.Prefix] = []

    root = tree.getroot()

    ontology_iri = root.attrib.get("ontologyIRI")

    elements = defaultdict(list)
    for element in root:
        elements[element.tag].append(element)

    # Step 1: get out all prefixes
    converter = Converter()
    # converter.add_prefix("obo", "http://purl.obolibrary.org/obo/")
    converter.add_prefix("orcid", "https://orcid.org/")
    for prefix_tag in elements.pop(_owl("Prefix"), []):
        curie_prefix, uri_prefix = prefix_tag.attrib["name"], prefix_tag.attrib["IRI"]
        converter.add_prefix(curie_prefix, uri_prefix)
        prefixes.append(Prefix(curie_prefix, uri_prefix))

    # Step 2: get out all declarations

    tag_to_declaration_type: dict[str, DeclarationType] = {
        f"{{http://www.w3.org/2002/07/owl#}}{t}": t for t in typing.get_args(DeclarationType)
    }
    for declaration_tag in elements.pop(_owl("Declaration"), []):
        for subelement in declaration_tag:
            match subelement.tag:
                case "{http://www.w3.org/2002/07/owl#}Class":
                    pass

            reference = _get_reference(converter, subelement)
            axioms.append(Declaration(reference, tag_to_declaration_type[subelement.tag]))

    # Step 3: get all annotations on the ontology itself
    annotation_tags = []
    for annotation_tag in elements.pop(_owl("Annotation"), []):
        property_tag = annotation_tag.find(_owl("AnnotationProperty"))
        property_ref = _get_reference(converter, property_tag)

        *_subannotations, target = list(annotation_tag)

        if not isinstance(target, Element):
            raise TypeError(f"unhandled target tag: {target}")

        match target.tag:
            case "{http://www.w3.org/2002/07/owl#}Literal":
                match annotation_tag.find("{http://www.w3.org/2002/07/owl#}Literal"):
                    case etree._Element() as element:
                        datatype = element.attrib.pop("datatypeIRI", None)
                        if element.attrib:
                            raise NotImplementedError(
                                f"unhandled attribs in Literal: {element.attrib}"
                            )
                        annotation_tags.append((property_ref, element.text, datatype))
                        _ola.append(
                            f.Annotation(
                                property_ref, rdflib.Literal(element.text, datatype=datatype)
                            )
                        )
                    case None:
                        pass
                    case _:
                        raise NotImplementedError("malformed Literal")
            case "{http://www.w3.org/2002/07/owl#}AbbreviatedIRI":
                target_ref = _tmfr(converter, target.text)
                _ola.append(f.Annotation(property_ref, target_ref))
            case "{http://www.w3.org/2002/07/owl#}IRI":
                target_ref = converter.parse_uri(target.text)
                if not target_ref:
                    box = rdflib.Literal(target.text, datatype=XSD.anyURI)
                    _ola.append(f.Annotation(property_ref, box))
                else:
                    _ola.append(f.Annotation(property_ref, target_ref.to_pydantic()))
            case _:
                raise NotImplementedError(
                    f"unhandled annotation tag, contains something besides Literal: {annotation_tag}"
                )

    for tag_name, axiom_cls in [
        ("SubClassOf", f.SubClassOf),
        ("SubAnnotationPropertyOf", f.SubAnnotationPropertyOf),
    ]:
        for tag in elements.pop(_owl(tag_name), []):
            *annotation_tags, child_tag, parent_tag = list(tag)
            if not isinstance(child_tag, Element):
                raise TypeError(f"unhandled child tag: {child_tag}")
            if not isinstance(parent_tag, Element):
                raise TypeError(f"unhandled parent tag: {parent_tag}")
            axioms.append(
                axiom_cls(
                    child=_get_reference(converter, child_tag),
                    parent=_get_reference(converter, parent_tag),
                    annotations=_parse_annotation_tags(annotation_tags, converter),
                )
            )

    for annotation_assertion_tag in elements.pop(_owl("AnnotationAssertion"), []):
        *annotation_tags, predicate_tag, subject_tag, object_tag = list(annotation_assertion_tag)
        predicate = _get_reference(converter, predicate_tag)

        subject: Reference
        if subject_tag.text.startswith("http"):
            subject = converter.parse_uri(subject_tag.text, strict=True).to_pydantic()
        else:
            subject = _tmfr(converter, subject_tag.text)

        match object_tag.tag:
            case "{http://www.w3.org/2002/07/owl#}Literal":
                obj = f.LiteralBox(object_tag.text)
            case "{http://www.w3.org/2002/07/owl#}IRI":
                obj = converter.parse_uri(object_tag.text, strict=True).to_pydantic()
            case "{http://www.w3.org/2002/07/owl#}AbbreviatedIRI":
                obj = _tmfr(converter, object_tag.text)
            case _:
                raise NotImplementedError(f"unhandled object tag: {object_tag.tag}")

        axioms.append(AnnotationAssertion(predicate, subject, obj, annotations=_ola))

    if elements:
        raise NotImplementedError(f"unhandled tags: {elements.keys()}")

    ontology = Ontology(
        iri=ontology_iri,
        version_iri=None,  # TODO extract from annotations
        annotations=_ola,
        axioms=axioms,
    )

    return Document(ontology, prefixes=prefixes)


def _get_reference(converter: Converter, element: Element) -> Reference:
    if uri := element.attrib.get("IRI"):
        rv = converter.parse_uri(uri, strict=True)
        return Reference.from_reference(rv)
    elif curie := element.attrib.get("abbreviatedIRI"):
        return _tmfr(converter, curie)
    else:
        raise ValueError(f"malformed declaration: {element} ({list(element)})")


def _tmfr(converter: Converter, curie: str) -> Reference:
    # TODO this operation for precisifying a CURIE should be
    #  in the converter, as part of the "standardize" operation
    uri = converter.expand(curie, strict=True)
    xx = converter.parse_uri(uri, strict=True)
    return xx.to_pydantic()


def _parse_annotation_tags(
    annotation_tags: Iterable[Element], converter: Converter
) -> list[Annotation]:
    rv = []  # TODO handle annotation tags
    for annotation_tag in annotation_tags:
        *subannotation_tags, predicate_tag, object_tag = list(annotation_tag)
        match object_tag.tag:
            case "{http://www.w3.org/2002/07/owl#}AbbreviatedIRI":
                obj = _tmfr(converter, object_tag.text)
            case _:
                raise NotImplementedError(f"unhandled annotation object type: {object_tag.tag}")
        predicate = _get_reference(converter, predicate_tag)
        subannotations = _parse_annotation_tags(subannotation_tags, converter)
        rv.append(Annotation(predicate, obj, annotations=subannotations))
    return rv


def _main() -> None:
    for prefix, path in [
        ("cvx", "/Users/cthoyt/dev/obo-db-ingest/export/cvx/cvx-owl-xml.xml"),
        ("cvx", "/Users/cthoyt/Downloads/cl-multilingual.owx"),
    ]:
        read_owl(prefix, path)
        # x.write_obo("/Users/cthoyt/Desktop/test.obo")


if __name__ == "__main__":
    _main()
