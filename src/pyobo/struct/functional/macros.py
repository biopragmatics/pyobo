"""Macros over functional OWL.

This module contains classes that are extensions
to functional OWL that reflect common usage.
"""

import typing as t
from typing import TypeAlias

import rdflib
from curies import Converter, Reference
from rdflib import DCTERMS, RDFS, Graph, term

from pyobo.struct.functional import dsl as f

__all__ = [
    "AltMacro",
    "DescriptionMacro",
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
    def __init__(self, box: f.Box):
        self.box = box

    def to_rdflib_node(self, graph: Graph, converter: Converter) -> term.Node:
        return self.box.to_rdflib_node(graph, converter)

    def to_funowl(self) -> str:
        return self.box.to_funowl()

    def to_funowl_args(self) -> str:
        raise RuntimeError


class RelationshipMacro(Macro):
    """A macro for an object-to-object relationship.

    Assert that the RAET1E gene from HGNC (16793) is
    only in the human taxon (9606)

    >>> RelationshipMacro("hgnc:16793", "RO:0002160", "NCBITaxon:9606").to_funowl()
    'SubClassOf( hgnc:16793 ObjectSomeValuesFrom( RO:0002160 NCBITaxon:9606 ) )'
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
    """A macro for label assertion."""

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
    """A macro for label assertion.

    >>> LabelMacro("hgnc:16793", "RAET1E").to_funowl()
    'AnnotationAssertion( rdfs:label hgnc:16793 "RAET1E" )'

    Assert the language:

    >>> LabelMacro("hgnc:16793", "RAET1E", language="en").to_funowl()
    'AnnotationAssertion( rdfs:label hgnc:16793 "RAET1E"@en )'
    """

    annotation_property: t.ClassVar[Reference] = Reference(prefix="rdfs", identifier="label")


class DescriptionMacro(StringMacro):
    """A macro for description assertion."""

    annotation_property: t.ClassVar[Reference] = Reference(prefix="dcterms", identifier="description")


class AltMacro(Macro):
    """A macro for alternate ID assertion."""

    predicate: t.ClassVar[Reference] = Reference(prefix="IAO", identifier="0000118")

    def __init__(self, s: f.IdentifierBoxOrHint, alt: f.IdentifierBoxOrHint) -> None:
        """Instatitate the alternate identifier assertion macro."""
        super().__init__(f.AnnotationAssertion(self.predicate, s, alt))


class IsObsoleteMacro(Macro):
    """A macro for obsoletion assertion."""

    def __init__(self, s: f.IdentifierBoxOrHint) -> None:
        """Instatitate the is obsolete assertion macro."""
        raise NotImplementedError


SynonymScope: TypeAlias = t.Literal["exact", "broad", "narrow"]
SYNONYM_SCOPES: dict[SynonymScope, Reference] = {
    "exact": Reference(prefix="oboInOwl", identifier="hasExactSynonym"),
    "broad": Reference(prefix="oboInOwl", identifier="hasBroadSynonym"),
    "narrow": Reference(prefix="oboInOwl", identifier="hasNarrowSynonym"),
}
HAS_SYNONYM_TYPE = Reference.from_curie("oboInOwl:hasSynonymType")

MappingScope: TypeAlias = t.Literal["exact", "broad", "narrow"]
MAPPING_SCOPES: dict[MappingScope, Reference] = {
    "exact": Reference(prefix="skos", identifier="exactMatch"),
    "broad": Reference(prefix="skos", identifier="broadMatch"),
    "narrow": Reference(prefix="skos", identifier="narrowMatch"),
}
HAS_MAPPING_JUSTIFICATION = Reference.from_curie("sssom:has_mapping_justification")


class SynonymMacro(Macro):
    """A macro for synonym assertion.

    >>> SynonymMacro("hgnc:16793", "exact", "ULBP4", synonym_type="OMO:0003008").to_funowl()
    'AnnotationAssertion( Annotation( oboInOwl:hasSynonymType OMO:0003008 ) oboInOwl:hasExactSynonym hgnc:16793 "ULBP4" )'
    """

    def __init__(
        self,
        subject: f.IdentifierBoxOrHint,
        scope: SynonymScope | f.IdentifierBoxOrHint,
        value: str | rdflib.Literal,
        *,
        language: str | None = None,
        annotations: f.Annotations | None = None,
        synonym_type: f.IdentifierBoxOrHint | None = None,
    ) -> None:
        """Instatitate the synonym annotation assertion macro."""
        if annotations is None:
            annotations = []
        if synonym_type is not None:
            annotations.append(f.Annotation(HAS_SYNONYM_TYPE, synonym_type))
        if scope in t.get_args(SynonymScope):
            scope = SYNONYM_SCOPES[scope]  # type:ignore[index]
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
    ...     "exact",
    ...     "agro:00000137",
    ...     mapping_justification="semapv:ManualMappingCuration",
    ... ).to_funowl()
    'AnnotationAssertion( Annotation( sssom:has_mapping_justification semapv:ManualMappingCuration ) skos:exactMatch agrovoc:0619dd9e agro:00000137 )'
    """

    def __init__(
        self,
        subject: f.IdentifierBoxOrHint,
        predicate: MappingScope | f.IdentifierBoxOrHint,
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
        if predicate in t.get_args(MappingScope):
            predicate = MAPPING_SCOPES[predicate]  # type:ignore[index]
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
    'AnnotationAssertion( oboInOwl:hasDbXref agrovoc:0619dd9e agro:00000137 )'
    """

    def __init__(
        self,
        subject: f.IdentifierBoxOrHint,
        target: f.IdentifierBoxOrHint,
        **kwargs: t.Any,
    ) -> None:
        """Instatitate the database cross-reference annotation assertion macro."""
        super().__init__(subject=subject, predicate="oboInOwl:hasDbXref", target=target, **kwargs)
