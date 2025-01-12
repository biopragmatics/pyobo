"""Converters from OBO to functional OWL."""

from __future__ import annotations

from collections import ChainMap
from collections.abc import Iterable
from typing import TYPE_CHECKING, cast

import rdflib
from curies import vocabulary as v
from rdflib import XSD

from pyobo.struct import Stanza
from pyobo.struct import vocabulary as pv
from pyobo.struct.functional import dsl as f
from pyobo.struct.functional import macros as m
from pyobo.struct.functional.ontology import Document, Ontology
from pyobo.struct.functional.utils import DEFAULT_PREFIX_MAP
from pyobo.struct.reference import OBOLiteral, Reference

if TYPE_CHECKING:
    from pyobo.struct.struct import Obo, Referenced, Term
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
    prefix = obo_ontology.ontology
    base = f"https://w3id.org/biopragmatics/resources/{prefix}"
    iri = f"{base}/{prefix}.ofn"
    if obo_ontology.data_version:
        version_iri = f"{base}/{obo_ontology.data_version}/{prefix}.ofn"
    else:
        version_iri = None
    ofn_ontology = Ontology(
        iri=iri,
        version_iri=version_iri,
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
        yield f.Declaration(pv.has_ontology_root_term, type="AnnotationProperty")
        yield m.LabelMacro(pv.has_ontology_root_term, cast(str, pv.has_ontology_root_term.name))

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
            yield f.ClassAssertion(parent.preferred_curie, s)
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
        yield m.ReplacedByMacro(alt.preferred_curie, s)
    # 6
    yield from _yield_definition(term, s)
    # 7 comment is covered by properties
    # 8
    for subset in term.subsets:
        yield m.OBOIsSubsetMacro(s, subset)
    # 9
    yield from _yield_synonyms(term, s)
    # 10
    yield from _yield_xrefs(term, s)
    # 11
    if term.builtin is not None:
        yield m.IsOBOBuiltinMacro(s, term.builtin)
    # 12
    yield from _yield_properties(term, s)
    # 13 parents - see top
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
    if term.disjoint_from:
        yield f.DisjointClasses([s, *term.disjoint_from])
    # 18
    for typedef, value in term.iterate_relations():
        rel_annotations = _get_annotations(term, typedef, value)
        if term.type == "Term":
            yield m.RelationshipMacro(
                s=s,
                p=typedef.preferred_curie,
                o=value.preferred_curie,
                annotations=rel_annotations,
            )
        else:
            yield f.ObjectPropertyAssertion(
                typedef.preferred_curie, s, value.preferred_curie, annotations=rel_annotations
            )

    # 19 TODO created_by
    # 20 TODO creation_date
    # 21
    if term.is_obsolete is not None:
        yield m.IsObsoleteMacro(s, term.is_obsolete)
    # 22 replaced_by is covered by properties
    # 23 consider is covered by properties


def _get_annotations(
    term: Stanza, p: Reference | Referenced, o: Reference | Referenced | OBOLiteral | str
) -> list[f.Annotation]:
    return _process_anns(term._get_annotations(p, o))


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
    # 5 the way this one works is that all of the alts get a term-replaced-by,
    #   as well as getting their own deprecation axioms
    for alt_id in typedef.alt_ids:
        yield m.ReplacedByMacro(alt_id, r)
    # 6
    yield from _yield_definition(typedef, r)
    # 7
    if typedef.comment:
        yield m.CommentMacro(r, typedef.comment)
    # 8
    for subset in typedef.subsets:
        yield m.OBOIsSubsetMacro(r, subset)
    # 9
    yield from _yield_synonyms(typedef, r)
    # 10
    yield from _yield_xrefs(typedef, r)
    # 11
    yield from _yield_properties(typedef, r)
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
    for chain in typedef.holds_over_chain:
        yield m.HoldsOverChain(r, chain)
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
        yield f.DisjointObjectProperties([x, r])
    # 28
    if typedef.inverse:
        yield f.InverseObjectProperties(r, typedef.inverse)
    # 29
    for to in typedef.transitive_over:
        yield m.TransitiveOver(r, to)
    # 30
    for chain in typedef.equivalent_to_chain:
        yield f.SubObjectPropertyOf(f.ObjectPropertyChain(chain), r)
    # 31 TODO disjoint_over, ROBOT does not create any output
    # 32 TODO relationship, ROBOT does not create any output
    # 33
    if typedef.is_obsolete is not None:
        yield m.IsObsoleteMacro(r, typedef.is_obsolete)
    # 34 TODO created_by
    # 35 TODO creation_date
    # 36
    for rep in typedef.get_replaced_by():
        yield m.ReplacedByMacro(rep, r)
    # 37
    for ref in typedef.get_see_also():
        yield m.OBOConsiderMacro(r, ref)
    # 38 TODO expand_assertion_to
    # 39 TODO expand_expression_to
    # 41
    if typedef.is_class_level is not None:
        yield m.OBOIsClassLevelMacro(r, typedef.is_class_level)


def _yield_definition(term: Stanza, s) -> Iterable[m.DescriptionMacro]:
    if term.definition:
        yield m.DescriptionMacro(
            s,
            term.definition,
            annotations=_get_annotations(term, pv.has_description, term.definition),
        )


def _yield_synonyms(stanza: Stanza, r) -> Iterable[m.SynonymMacro]:
    for synonym in stanza.synonyms:
        yield m.SynonymMacro(
            r,
            synonym.name,
            scope=synonym.specificity,
            synonym_type=synonym.type,
            provenance=synonym.provenance,
            annotations=_process_anns(synonym.annotations),
        )


def _yield_xrefs(term: Stanza, s) -> Iterable[m.XrefMacro]:
    for xref in term.xrefs:
        yield m.XrefMacro(
            s, xref.preferred_curie, annotations=_get_annotations(term, pv.has_dbxref, xref)
        )


_SKIP = {
    # we skip alt terms since OFN
    # prefers to flip the triple and use term-replaced-by instead
    pv.alternative_term,
}


def _yield_properties(term: Stanza, s) -> Iterable[f.AnnotationAssertion]:
    for typedef, values in term.properties.items():
        ty_pc = typedef.preferred_curie
        for value in values:
            annotations = _get_annotations(term, typedef, value)
            match value:
                case OBOLiteral():
                    yield f.AnnotationAssertion(
                        ty_pc,
                        s,
                        _oboliteral_to_literal(value),
                        annotations=annotations,
                    )
                case Reference():
                    if typedef in _SKIP:
                        continue
                    yield f.AnnotationAssertion(
                        ty_pc,
                        s,
                        value.preferred_curie,
                        annotations=annotations,
                    )