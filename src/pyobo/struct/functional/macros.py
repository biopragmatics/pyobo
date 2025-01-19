"""Macros over functional OWL.

This module contains classes that are extensions
to functional OWL that reflect common usage.
"""

import typing as t
from collections.abc import Sequence

import rdflib
from curies import Converter, Reference
from curies import vocabulary as v
from rdflib import Graph, term

from pyobo.struct import vocabulary as pv
from pyobo.struct.functional import dsl as f

__all__ = [
    "AltMacro",
    "DescriptionMacro",
    "IsAnonymousMacro",
    "IsObsoleteMacro",
    "LabelMacro",
    "MappingMacro",
    "RelationshipMacro",
    "SynonymMacro",
    "XrefMacro",
]


def _safe_literal(value: str | rdflib.Literal, *, language: str | None = None) -> rdflib.Literal:
    if isinstance(value, rdflib.Literal):
        return value
    return rdflib.Literal(value, lang=language)


class Macro(f.Box):
    """A macro, which wraps a more complicated set of functional OWL axioms."""

    def __init__(self, box: f.Box):
        """Initialize the macro with a given axiom."""
        self.box = box

    def to_rdflib_node(self, graph: Graph, converter: Converter) -> term.IdentifiedNode:
        """Make an RDF node for the wrapped axiom."""
        return self.box.to_rdflib_node(graph, converter)

    def to_funowl(self) -> str:
        """Serialize functional OWL for the wrapped axiom."""
        return self.box.to_funowl()

    def to_funowl_args(self) -> str:  # pragma: no cover
        """Get the inside of the functional OWL tag representing the wrapped axiom (unused)."""
        raise RuntimeError


class RelationshipMacro(Macro):
    """A macro for an object-to-object relationship.

    Assert that the RAET1E gene from HGNC (16793) is
    only in the human taxon (9606)

    >>> RelationshipMacro("hgnc:16793", "RO:0002160", "NCBITaxon:9606").to_funowl()
    'SubClassOf(hgnc:16793 ObjectSomeValuesFrom(RO:0002160 NCBITaxon:9606))'
    """

    def __init__(
        self,
        s: f.IdentifierBoxOrHint,
        p: f.IdentifierBoxOrHint,
        o: f.IdentifierBoxOrHint,
        *,
        annotations: f.Annotations | None = None,
    ) -> None:
        """Instantiate the object-to-object SubClassOf macro."""
        super().__init__(f.SubClassOf(s, f.ObjectSomeValuesFrom(p, o)))


class StringMacro(Macro):
    """A macro for string assertion."""

    annotation_property: t.ClassVar[rdflib.URIRef | Reference]

    def __init__(
        self,
        subject: f.IdentifierBoxOrHint,
        value: str | rdflib.Literal,
        *,
        language: str | None = None,
        annotations: f.Annotations | None = None,
    ) -> None:
        """Instatitate the string assertion macro."""
        super().__init__(
            f.AnnotationAssertion(
                self.annotation_property,
                subject,
                _safe_literal(value, language=language),
                annotations=annotations,
            )
        )


class LabelMacro(StringMacro):
    """A macro for label string assertion.

    >>> LabelMacro("hgnc:16793", "RAET1E").to_funowl()
    'AnnotationAssertion(rdfs:label hgnc:16793 "RAET1E")'

    Assert the language:

    >>> LabelMacro("hgnc:16793", "RAET1E", language="en").to_funowl()
    'AnnotationAssertion(rdfs:label hgnc:16793 "RAET1E"@en)'
    """

    annotation_property = pv.label


class DescriptionMacro(StringMacro):
    """A macro for description string assertion.

    >>> DescriptionMacro("hgnc:16793", "retinoic acid early transcript 1E").to_funowl()
    'AnnotationAssertion(dcterms:description hgnc:16793 "retinoic acid early transcript 1E")'
    """

    annotation_property = pv.has_description


class CommentMacro(StringMacro):
    """A macro for comment string assertion."""

    annotation_property = pv.comment


class OBONamespaceMacro(StringMacro):
    """A macro for OBO namespace string assertion."""

    annotation_property = pv.has_obo_namespace


class ObjectAnnotationMacro(Macro):
    """A macro for annotation properties."""

    annotation_property: t.ClassVar[Reference]

    def __init__(self, subject: f.IdentifierBoxOrHint, target: f.IdentifierBoxOrHint) -> None:
        """Instatitate the annotation assertion macro."""
        super().__init__(f.AnnotationAssertion(self.annotation_property, subject, target))


class AltMacro(ObjectAnnotationMacro):
    """A macro for alternate ID assertion."""

    annotation_property = pv.alternative_term


class ReplacedByMacro(ObjectAnnotationMacro):
    """A macro for replaced by assertion."""

    annotation_property = pv.term_replaced_by


class OBOConsiderMacro(ObjectAnnotationMacro):
    """A macro for OBO consider assertion."""

    # FIXME replace with see also
    annotation_property = Reference(prefix="oboInOwl", identifier="consider")


class OBOIsSubsetMacro(ObjectAnnotationMacro):
    """A macro for OBO "in subset" assertion."""

    annotation_property = pv.in_subset


class BooleanAnnotationMacro(Macro):
    """A macro for an annotation assertion with a boolean as its object."""

    annotation_property: t.ClassVar[Reference]

    def __init__(self, subject: f.IdentifierBoxOrHint, value: bool = True) -> None:
        """Instatitate the annotation assertion macro, defaults to "true"."""
        super().__init__(
            f.AnnotationAssertion(self.annotation_property, subject, f.LiteralBox(value))
        )


class IsAnonymousMacro(BooleanAnnotationMacro):
    """A macro for an "is anonymous" assertion."""

    annotation_property = Reference(prefix="oboInOwl", identifier="is_anonymous")


class IsOBOBuiltinMacro(BooleanAnnotationMacro):
    """A macro for an "builtin" assertion."""

    annotation_property = Reference(prefix="oboInOwl", identifier="builtin")


class OBOIsClassLevelMacro(BooleanAnnotationMacro):
    """A macro for OBO "is class level" assertion."""

    annotation_property = Reference(prefix="oboInOwl", identifier="is_class_level")


class IsObsoleteMacro(BooleanAnnotationMacro):
    """A macro for obsoletion assertion."""

    annotation_property = Reference(prefix="owl", identifier="deprecated")


class IsCyclic(BooleanAnnotationMacro):
    """A macro for "is cyclic" assertion."""

    annotation_property = Reference(prefix="oboInOwl", identifier="is_cyclic")


HAS_SYNONYM_TYPE = Reference.from_curie("oboInOwl:hasSynonymType")
HAS_MAPPING_JUSTIFICATION = Reference.from_curie("sssom:has_mapping_justification")


class SynonymMacro(Macro):
    """A macro for synonym assertion.

    You can just make a quick assertion, which defaults to ``RELATED``:

    >>> SynonymMacro("hgnc:16793", "ULBP4").to_funowl()
    'AnnotationAssertion(oboInOwl:hasRelatedSynonym hgnc:16793 "ULBP4")'

    You can make the predicate more explicit either with OBO-style
    scoping (``EXACT``, ``BROAD``, ``NARROW``, ``RELATED``) or a CURIE/:class:`curies.Reference`/URIRef

    >>> SynonymMacro("hgnc:16793", "ULBP4", "EXACT").to_funowl()
    'AnnotationAssertion(oboInOwl:hasExactSynonym hgnc:16793 "ULBP4")'

    You can add a synonym type from OMO:

    >>> SynonymMacro("hgnc:16793", "ULBP4", "EXACT", synonym_type="OMO:0003008").to_funowl()
    'AnnotationAssertion(Annotation(oboInOwl:hasSynonymType OMO:0003008) oboInOwl:hasExactSynonym hgnc:16793 "ULBP4")'
    """

    def __init__(
        self,
        subject: f.IdentifierBoxOrHint,
        value: str | rdflib.Literal,
        scope: v.SynonymScope | f.IdentifierBoxOrHint | None = None,
        *,
        language: str | None = None,
        annotations: f.Annotations | None = None,
        synonym_type: f.IdentifierBoxOrHint | None = None,
        provenance: Sequence[f.PrimitiveHint] | None = None,
    ) -> None:
        """Instatitate the synonym annotation assertion macro."""
        if annotations is None:
            annotations = []
        if provenance:
            annotations.extend(f.Annotation(pv.has_dbxref, r) for r in provenance)
        if synonym_type is not None:
            annotations.append(f.Annotation(HAS_SYNONYM_TYPE, synonym_type))
        if scope is None:
            scope = v.has_related_synonym
        elif isinstance(scope, str) and scope.upper() in t.get_args(v.SynonymScope):
            scope = v.synonym_scopes[scope.upper()]  # type:ignore[index]
        super().__init__(
            f.AnnotationAssertion(
                scope,
                subject,
                _safe_literal(value, language=language),
                annotations=annotations,
            )
        )


class MappingMacro(Macro):
    """A macro for mapping assertion.

    >>> MappingMacro(
    ...     "agrovoc:0619dd9e",
    ...     "EXACT",
    ...     "agro:00000137",
    ...     mapping_justification="semapv:ManualMappingCuration",
    ... ).to_funowl()
    'AnnotationAssertion(Annotation(sssom:has_mapping_justification semapv:ManualMappingCuration) skos:exactMatch agrovoc:0619dd9e agro:00000137)'
    """

    def __init__(
        self,
        subject: f.IdentifierBoxOrHint,
        predicate: v.SemanticMappingScope | f.IdentifierBoxOrHint,
        target: f.IdentifierBoxOrHint,
        *,
        annotations: f.Annotations | None = None,
        mapping_justification: f.IdentifierBoxOrHint | None = None,
    ) -> None:
        """Instatitate the mapping annotation assertion macro."""
        if annotations is None:
            annotations = []
        if mapping_justification is not None:
            # FIXME check mapping justification is from semapv
            annotations.append(f.Annotation(HAS_MAPPING_JUSTIFICATION, mapping_justification))
        if isinstance(predicate, str) and predicate.upper() in t.get_args(v.SemanticMappingScope):
            predicate = v.semantic_mapping_scopes[predicate.upper()]  # type:ignore[index]
        super().__init__(
            f.AnnotationAssertion(
                predicate,
                subject,
                target,
                annotations=annotations,
            )
        )


class XrefMacro(MappingMacro):
    """A macro for database cross-reference assertion, based on the more generic Mapping macro.

    >>> XrefMacro("agrovoc:0619dd9e", "agro:00000137").to_funowl()
    'AnnotationAssertion(oboInOwl:hasDbXref agrovoc:0619dd9e agro:00000137)'
    """

    def __init__(
        self,
        subject: f.IdentifierBoxOrHint,
        target: f.IdentifierBoxOrHint,
        **kwargs: t.Any,
    ) -> None:
        """Instatitate the database cross-reference annotation assertion macro."""
        super().__init__(subject=subject, predicate="oboInOwl:hasDbXref", target=target, **kwargs)


class HoldsOverChain(Macro):
    """A macro for the OBO-style "holds over chain" annotation."""

    def __init__(self, predicate: f.IdentifierBoxOrHint, chain: Sequence[f.IdentifierBoxOrHint]):
        """Instantiate a "holds over chain" macro."""
        super().__init__(f.SubObjectPropertyOf(f.ObjectPropertyChain(chain), predicate))


class TransitiveOver(HoldsOverChain):
    """A macro for the OBO-style "transitive over" annotation.

    For example, ``BFO:0000066`` (occurs in) is transitive over
    ``BFO:0000050`` (part of). This means that if X occurs in Y,
    and Y is a part of Z, then X occurs in Z.

    >>> TransitiveOver("BFO:0000066", "BFO:0000050").to_funowl()
    'SubObjectPropertyOf(ObjectPropertyChain(BFO:0000066 BFO:0000050) BFO:0000066)'

    .. note:: This is a special case of :class:`HoldsOverChain`
    """

    def __init__(self, predicate: f.IdentifierBoxOrHint, target: f.IdentifierBoxOrHint):
        """Instantiate a "transitive over" macro."""
        super().__init__(predicate, [predicate, target])


class DataPropertyMaxCardinality(Macro):
    r"""A macro over :class:`DataMaxCardinality` that adds an axiom.

    For example, each person can be annotated with a maximum of one age.
    This can be represented as:

    >>> DataPropertyMaxCardinality(1, "a:hasAge").to_funowl()
    'SubClassOf(owl:Thing DataMaxCardinality(1 a:hasAge))'
    """

    def __init__(
        self,
        cardinality: int,
        data_property_expression: f.DataPropertyExpression | f.IdentifierBoxOrHint,
    ):
        """Initialize a data property maximum cardinality macro."""
        super().__init__(
            f.SubClassOf(
                "owl:Thing",
                f.DataMaxCardinality(
                    cardinality=cardinality, data_property_expression=data_property_expression
                ),
            )
        )


class ObjectListOfMacro(Macro):
    """An object list macro."""

    object_list_cls: t.ClassVar[type[f._ObjectList]]

    def __init__(
        self,
        term: f.IdentifierBoxOrHint,
        elements: Sequence[
            f.IdentifierBoxOrHint | tuple[f.IdentifierBoxOrHint, f.IdentifierBoxOrHint]
        ],
    ) -> None:
        """Instantiate an "intersection of" macro."""
        expressions: list[f.ClassExpression | f.IdentifierBoxOrHint] = []
        for element in elements:
            if isinstance(element, tuple):
                expressions.append(
                    f.ObjectSomeValuesFrom(f.IdentifierBox(element[0]), f.IdentifierBox(element[1]))
                )
            else:
                expressions.append(element)

        super().__init__(
            f.EquivalentClasses([f.IdentifierBox(term), self.object_list_cls(expressions)])
        )


class ClassIntersectionMacro(ObjectListOfMacro):
    """A macro that represents a class intersection.

    >>> ClassIntersectionMacro(
    ...     "ZFA:0000134", ["CL:0000540", ("BFO:0000050", "NCBITaxon:7955")]
    ... ).to_funowl()
    'EquivalentClasses(ZFA:0000134 ObjectIntersectionOf(CL:0000540 ObjectSomeValuesFrom(BFO:0000050 NCBITaxon:7955)))'
    """

    object_list_cls = f.ObjectIntersectionOf


class ClassUnionMacro(ObjectListOfMacro):
    """A macro that represents a class union."""

    object_list_cls = f.ObjectUnionOf
