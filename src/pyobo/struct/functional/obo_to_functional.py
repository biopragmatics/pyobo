"""Converters from OBO to functional OWL."""

from __future__ import annotations

from collections.abc import Iterable
from typing import TYPE_CHECKING

import curies
from rdflib import XSD, Literal

from pyobo.struct.functional import dsl as f
from pyobo.struct.functional import macros as m

if TYPE_CHECKING:
    from pyobo.struct.struct import Term
    from pyobo.struct.typedef import TypeDef

__all__ = [
    "get_term_axioms",
    "get_typedef_axioms",
]


def get_term_axioms(term: Term) -> Iterable[f.Box]:
    """Iterate over functional OWL axioms for a term."""
    s = f.IdentifierBox(term.reference.preferred_curie)
    if term.type == "Term":
        yield f.Declaration(s, type="Class")
        for parent in term.parents:
            yield f.SubClassOf(s, parent.preferred_curie)
    else:
        yield f.Declaration(s, type="NamedIndividual")
        for parent in term.parents:
            yield f.ClassAssertion(s, parent.preferred_curie)
    if term.name:
        yield m.LabelMacro(s, term.name)
    if term.definition:
        yield m.DescriptionMacro(s, term.definition)
    for alt in term.alt_ids:
        yield m.AltMacro(s, alt.preferred_curie)
    # TODO add annotations for the following
    for xref in term.xrefs:
        yield m.XrefMacro(s, xref.preferred_curie)
    for typedef, value in term.iterate_relations():
        yield m.RelationshipMacro(s=s, p=typedef.preferred_curie, o=value.preferred_curie)
    for typedef, values in term.annotations_object.items():
        for value in values:
            yield f.AnnotationAssertion(typedef.preferred_curie, s, value.preferred_curie)
    for typedef, literal_values in term.annotations_literal.items():
        for str_value, dtype in literal_values:
            # make URIRef for datatype
            if dtype.prefix == "xsd":
                datatype = XSD._NS.term(dtype.identifier)
            else:
                raise NotImplementedError
            literal = Literal(str_value, datatype=datatype)
            yield f.AnnotationAssertion(typedef.preferred_curie, s, literal)


def get_typedef_axioms(typedef: TypeDef) -> Iterable[f.Box]:
    """Iterate over functional OWL axioms for a typedef."""
    r = f.IdentifierBox(typedef.preferred_curie)
    # 40
    if typedef.is_metadata_tag:
        yield f.Declaration(r, type="AnnotationProperty")
    else:
        yield f.Declaration(r, type="ObjectProperty")
    # 2
    if typedef.is_anonymous:
        yield m.IsAnonymousMacro(r)
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
            synonym.specificity,
            synonym.name,
            synonym_type=synonym.type,
        )
    # 10
    for xref in typedef.xrefs:
        yield m.XrefMacro(r, f.IdentifierBox(xref.preferred_curie))
    # 11
    for predicate, values in typedef.properties.items():
        for value in values:
            if isinstance(value, curies.Reference):
                yield f.AnnotationAssertion(r, predicate, value)
            else:
                raise NotImplementedError(f"not implemented to convert {value}")
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
    if typedef.builtin:
        yield m.IsOBOBuiltinMacro(r)
    # 15
    if typedef.holds_over_chain:
        yield m.HoldsOverChain(r, typedef.holds_over_chain)
    # 16
    if typedef.is_anti_symmetric:
        yield f.AsymmetricObjectProperty(r)
    # 17
    if typedef.is_cyclic:
        yield m.IsCyclic(r)
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
    # 24 TODO intersection_of
    # 25 TODO union_of
    # 26 TODO equivalent_to
    # 27 TODO disjoint_from
    # 28
    if typedef.inverse:
        yield f.InverseObjectProperties(r, typedef.inverse)
    # 29
    for to in typedef.transitive_over:
        yield m.TransitiveOver(r, to)
    # 30 TODO equivalent_to_chain
    # 31 TODO disjoint_over
    # 32 TODO relationship
    # 33
    if typedef.is_obsolete:
        yield m.IsObsoleteMacro(r)
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
    if typedef.is_class_level:
        yield m.OBOIsClassLevelMacro(r)
