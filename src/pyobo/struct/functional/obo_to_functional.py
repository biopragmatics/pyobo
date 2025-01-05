"""Converters from OBO to functional OWL."""

from __future__ import annotations

from collections.abc import Iterable
from typing import TYPE_CHECKING

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
    from pyobo.struct.struct import DEFAULT_SYNONYM_TYPE

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
            synonym.specificity,
            synonym.name,
            synonym_type=synonym.type if synonym.type != DEFAULT_SYNONYM_TYPE else None,
        )
    # 10
    # TODO add annotations for the following
    for xref in term.xrefs:
        yield m.XrefMacro(s, xref.preferred_curie)
    # 11
    if term.builtin is not None:
        yield m.IsOBOBuiltinMacro(s, term.builtin)
    # 12
    for typedef, values in term.annotations_object.items():
        for value in values:
            yield f.AnnotationAssertion(typedef.preferred_curie, s, value.preferred_curie)
    for typedef, literal_values in term.annotations_literal.items():
        for str_value, dtype in literal_values:
            # make URIRef for datatype
            if dtype.prefix == "xsd":
                datatype = XSD._NS.term(dtype.identifier)
            else:
                raise NotImplementedError(
                    f"Automatic literal conversion is not implemented for prefix: {dtype.prefix}"
                )
            literal = Literal(str_value, datatype=datatype)
            yield f.AnnotationAssertion(typedef.preferred_curie, s, literal)
    # 14 intersection_of
    # 15 union_of
    # 16 equivalent_to
    # 17 disjoint_from
    # 18
    for typedef, value in term.iterate_relations():
        yield m.RelationshipMacro(s=s, p=typedef.preferred_curie, o=value.preferred_curie)
    # 19 TODO created_by
    # 20 TODO creation_date
    # 21
    if term.is_obsolete is not None:
        yield m.IsObsoleteMacro(s, term.is_obsolete)
    # 22 TODO replaced_by
    # 23 TODO consider


def get_typedef_axioms(typedef: TypeDef) -> Iterable[f.Box]:
    """Iterate over functional OWL axioms for a typedef."""
    from pyobo.struct.struct import DEFAULT_SYNONYM_TYPE

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
            synonym.specificity,
            synonym.name,
            synonym_type=synonym.type if synonym.type != DEFAULT_SYNONYM_TYPE else None,
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
