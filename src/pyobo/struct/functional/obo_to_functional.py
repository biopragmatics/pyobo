"""Converters from OBO to functional OWL."""

from __future__ import annotations

from collections import ChainMap
from collections.abc import Iterable
from typing import TYPE_CHECKING, cast

import rdflib
from curies import vocabulary as v
from rdflib import XSD

from pyobo.struct.functional import dsl as f
from pyobo.struct.functional import macros as m
from pyobo.struct.functional.ontology import Document, Ontology
from pyobo.struct.functional.utils import DEFAULT_PREFIX_MAP
from pyobo.struct.reference import OBOLiteral, Reference
from pyobo.struct.vocabulary import has_ontology_root_term, has_dbxref

if TYPE_CHECKING:
    from pyobo.struct.struct import Obo, Term
    from pyobo.struct.struct_utils import Annotation as OBOAnnotation
    from pyobo.struct.typedef import TypeDef

__all__ = [
    "get_ofn_from_obo",
    "get_ontology_annotations",
    "get_ontology_axioms",
    "get_term_axioms",
    "get_typedef_axioms",
]


def get_ofn_from_obo(obo_ontology: Obo) -> Document:
    """Convert an ontology."""
    ofn_ontology = Ontology(
        iri=obo_ontology.ontology,
        # TODO is there a way to generate a version IRI?
        annotations=list(get_ontology_annotations(obo_ontology)),
        axioms=list(get_ontology_axioms(obo_ontology)),
    )
    document = Document(
        ofn_ontology,
        dict(
            ChainMap(
                DEFAULT_PREFIX_MAP,
                dict(obo_ontology.idspaces or {}),
            )
        ),
    )
    return document


def get_ontology_axioms(obo_ontology: Obo) -> Iterable[f.Box]:
    """Get axioms from the ontology."""
    if obo_ontology.root_terms:
        yield f.Declaration(has_ontology_root_term, type="AnnotationProperty")
        yield m.LabelMacro(has_ontology_root_term, cast(str, has_ontology_root_term.name))

    if obo_ontology.subsetdefs:
        yield f.Declaration("oboInOwl:SubsetProperty", type="AnnotationProperty")
        for subset_typedef, subset_label in obo_ontology.subsetdefs:
            yield f.Declaration(subset_typedef, type="AnnotationProperty")
            yield m.LabelMacro(subset_typedef, subset_label)
            yield f.SubAnnotationPropertyOf(subset_typedef, "oboInOwl:SubsetProperty")

    if obo_ontology.synonym_typedefs:
        yield f.Declaration("oboInOwl:hasScope", type="AnnotationProperty")
        for synonym_typedef in obo_ontology.synonym_typedefs:
            yield f.Declaration(synonym_typedef.reference, type="AnnotationProperty")
            yield m.LabelMacro(synonym_typedef.reference, synonym_typedef.name)
            yield f.SubAnnotationPropertyOf(
                synonym_typedef.reference, "oboInOwl:SynonymTypeProperty"
            )
            if synonym_typedef.specificity:
                yield f.AnnotationAssertion(
                    "oboInOwl:hasScope",
                    synonym_typedef.reference,
                    v.synonym_scopes[synonym_typedef.specificity],
                )

    for typedef in obo_ontology.typedefs or []:
        yield from get_typedef_axioms(typedef)

    for term in obo_ontology:
        yield from get_term_axioms(term)


def get_ontology_annotations(obo_ontology: Obo) -> Iterable[f.Annotation]:
    """Get annotations from the ontology."""
    for predicate, value in obo_ontology._iterate_property_pairs():
        yield f.Annotation(predicate, value)


def _oboliteral_to_literal(obo_literal) -> rdflib.Literal:
    if obo_literal.datatype.prefix == "xsd":
        datatype = XSD._NS.term(obo_literal.datatype.identifier)
    else:
        raise NotImplementedError(
            f"Automatic literal conversion is not implemented for prefix: {obo_literal.datatype.prefix}"
        )
    return rdflib.Literal(obo_literal.value, datatype=datatype)


def get_term_axioms(term: Term) -> Iterable[f.Box]:
    """Iterate over functional OWL axioms for a term."""
    s = f.IdentifierBox(term.reference.preferred_curie)
    # 1 and 13
    if term.type == "Term":
        yield f.Declaration(s, type="Class")
        for parent in term.parents:
            yield f.SubClassOf(s, parent.preferred_curie)
    else:
        yield f.Declaration(s, type="NamedIndividual")
        for parent in term.parents:
            yield f.ClassAssertion(s, parent.preferred_curie)
    # 2
    if term.is_anonymous is not None:
        yield m.IsAnonymousMacro(s, term.is_anonymous)
    # 3
    if term.name:
        yield m.LabelMacro(s, term.name)
    # 4
    if term.namespace:
        yield m.OBONamespaceMacro(s, term.namespace)
    # 5
    for alt in term.alt_ids:
        yield m.AltMacro(s, alt.preferred_curie)
    # 6
    if term.definition:
        yield m.DescriptionMacro(s, term.definition)
    # 7 TODO comment
    # 8
    for subset in term.subsets:
        yield m.OBOIsSubsetMacro(s, subset)
    # 9
    for synonym in term.synonyms:
        yield m.SynonymMacro(
            s,
            synonym.name,
            scope=synonym.specificity,
            synonym_type=synonym.type,
            annotations=_process_anns(synonym.annotations),
        )
    # 10
    # TODO add annotations for the following
    for xref in term.xrefs:
        yield m.XrefMacro(s, xref.preferred_curie, annotations=_get_annotations(term, has_dbxref, xref))
    # 11
    if term.builtin is not None:
        yield m.IsOBOBuiltinMacro(s, term.builtin)
    # 12
    for typedef, values in term.properties.items():
        for value in values:
            annotations = _get_annotations(term, typedef, value)
            match value:
                case OBOLiteral():
                    yield f.AnnotationAssertion(
                        typedef.preferred_curie,
                        s,
                        _oboliteral_to_literal(value),
                        annotations=annotations,
                    )
                case Reference():
                    yield f.AnnotationAssertion(
                        typedef.preferred_curie,
                        s,
                        value.preferred_curie,
                        annotations=annotations,
                    )
    # 14
    if term.intersection_of:
        yield m.ClassIntersectionMacro(s, term.intersection_of)
    # 15
    if term.union_of:
        yield m.ClassUnionMacro(s, term.union_of)
    # 16
    if term.equivalent_to:
        yield f.EquivalentClasses([s, *term.equivalent_to])
    # 17
    for x in term.disjoint_from:
        yield f.DisjointClasses(x, s)
    # 18
    for typedef, value in term.iterate_relations():
        yield m.RelationshipMacro(s=s, p=typedef.preferred_curie, o=value.preferred_curie, annotations=_get_annotations(term, typedef, value))
    # 19 TODO created_by
    # 20 TODO creation_date
    # 21
    if term.is_obsolete is not None:
        yield m.IsObsoleteMacro(s, term.is_obsolete)
    # 22 TODO replaced_by
    # 23 TODO consider


def _get_annotations(term: Term, p, o) -> list[f.Annotation]:
    return _process_anns(term._get_axioms(p, o))


def _process_anns(annotations: list[OBOAnnotation]) -> list[f.Annotation]:
    """Convert OBO anotations to OFN annotations."""
    return [_convert_annotation(a) for a in annotations]


def _convert_annotation(annotation: OBOAnnotation) -> f.Annotation:
    """Convert OBO anotations to OFN annotations."""
    match annotation.value:
        case OBOLiteral():
            return f.Annotation(
                annotation.predicate,
                _oboliteral_to_literal(annotation.value),
            )
        case Reference():
            return f.Annotation(
                annotation.predicate,
                annotation.value,
            )
    raise TypeError


def get_typedef_axioms(typedef: TypeDef) -> Iterable[f.Box]:
    """Iterate over functional OWL axioms for a typedef."""
    r = f.IdentifierBox(typedef.preferred_curie)
    # 40
    if typedef.is_metadata_tag:
        yield f.Declaration(r, type="AnnotationProperty")
    else:
        yield f.Declaration(r, type="ObjectProperty")
    # 2
    if typedef.is_anonymous is not None:
        yield m.IsAnonymousMacro(r, typedef.is_anonymous)
    # 3
    if typedef.name:
        yield m.LabelMacro(r, typedef.name)
    # 4
    if typedef.namespace:
        yield m.OBONamespaceMacro(r, typedef.namespace)
    # 5
    for alt_id in typedef.alt_id:
        yield m.AltMacro(r, alt_id)
    # 6
    if typedef.definition:
        yield m.DescriptionMacro(r, typedef.definition)
    # 7
    if typedef.comment:
        yield m.CommentMacro(r, typedef.comment)
    # 8
    for subset in typedef.subsets:
        yield m.OBOIsSubsetMacro(r, subset)
    # 9
    for synonym in typedef.synonyms:
        yield m.SynonymMacro(
            r,
            synonym.name,
            scope=synonym.specificity,
            synonym_type=synonym.type,
        )
    # 10
    for xref in typedef.xrefs:
        yield m.XrefMacro(r, f.IdentifierBox(xref.preferred_curie))
    # 11
    for predicate, values in typedef.properties.items():
        for value in values:
            yield f.AnnotationAssertion(r, predicate, value)
    # 12
    if typedef.domain:
        if typedef.is_metadata_tag:
            yield f.AnnotationPropertyDomain(r, typedef.domain)
        else:
            yield f.ObjectPropertyDomain(r, typedef.domain)
    # 13
    if typedef.range:
        if typedef.is_metadata_tag:
            yield f.AnnotationPropertyRange(r, typedef.range)
        else:
            yield f.ObjectPropertyRange(r, typedef.range)
    # 14
    if typedef.builtin is not None:
        yield m.IsOBOBuiltinMacro(r, typedef.builtin)
    # 15
    if typedef.holds_over_chain:
        yield m.HoldsOverChain(r, typedef.holds_over_chain)
    # 16
    if typedef.is_anti_symmetric:
        yield f.AsymmetricObjectProperty(r)
    # 17
    if typedef.is_cyclic is not None:
        yield m.IsCyclic(r, typedef.is_cyclic)
    # 18
    if typedef.is_reflexive:
        yield f.ReflexiveObjectProperty(r)
    # 19
    if typedef.is_symmetric:
        yield f.SymmetricObjectProperty(r)
    # 20
    if typedef.is_transitive:
        yield f.TransitiveObjectProperty(r)
    # 21
    if typedef.is_functional:
        yield f.FunctionalObjectProperty(r)
    # 22
    if typedef.is_inverse_functional:
        yield f.InverseFunctionalObjectProperty(r)
    # 23
    for parent in typedef.parents:
        if typedef.is_metadata_tag:
            yield f.SubAnnotationPropertyOf(r, parent)
        else:
            yield f.SubObjectPropertyOf(r, parent)
    # 24 TODO intersection_of, ROBOT does not create any output
    # 25 TODO union_of, ROBOT does not create any output
    # 26
    if typedef.equivalent_to:
        yield f.EquivalentObjectProperties([r, *typedef.equivalent_to])
    # 27
    for x in typedef.disjoint_from:
        yield f.DisjointObjectProperties(x, r)
    # 28
    if typedef.inverse:
        yield f.InverseObjectProperties(r, typedef.inverse)
    # 29
    for to in typedef.transitive_over:
        yield m.TransitiveOver(r, to)
    # 30
    if typedef.equivalent_to_chain:
        yield f.SubObjectPropertyOf(f.ObjectPropertyChain(typedef.equivalent_to_chain), r)
    # 31 TODO disjoint_over, ROBOT does not create any output
    # 32 TODO relationship, ROBOT does not create any output
    # 33
    if typedef.is_obsolete is not None:
        yield m.IsObsoleteMacro(r, typedef.is_obsolete)
    # 34 TODO created_by
    # 35 TODO creation_date
    # 36
    for rep in typedef.replaced_by:
        yield m.ReplacedByMacro(r, rep)
    # 37
    for ref in typedef.consider:
        yield m.OBOConsiderMacro(r, ref)
    # 38 TODO expand_assertion_to
    # 39 TODO expand_expression_to
    # 41
    if typedef.is_class_level is not None:
        yield m.OBOIsClassLevelMacro(r, typedef.is_class_level)
