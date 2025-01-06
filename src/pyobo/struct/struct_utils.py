"""Utiltites on top of the reference."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from typing import NamedTuple, TypeAlias

import curies
from typing_extensions import Self

from . import vocabulary as v
from .reference import (
    OBOLiteral,
    Reference,
    Referenced,
    default_reference,
    multi_reference_escape,
    reference_escape,
)

__all__ = [
    "AxiomsHint",
    "LiteralProperty",
    "ObjectProperty",
    "ReferenceHint",
    "Stanza",
]

AxiomsHint: TypeAlias = dict[
    tuple[Reference, Reference | OBOLiteral], list[tuple[Reference, Reference | OBOLiteral]]
]


class ObjectProperty(NamedTuple):
    """A tuple representing a propert with an object."""

    predicate: Reference
    object: Reference


class LiteralProperty(NamedTuple):
    """A tuple representing a property with a literal value."""

    predicate: Reference
    literal: OBOLiteral

    @classmethod
    def float(cls, predicate: Reference, value: float) -> Self:
        """Return a literal property for a float."""
        return cls(predicate, OBOLiteral(str(value), Reference(prefix="xsd", identifier="float")))


class Stanza:
    """A high-level class for stanzas."""

    relationships: dict[Reference, list[Reference]]
    xrefs: list[Reference]
    parents: list[Reference]
    provenance: list[Reference]
    intersection_of: list[Reference | ObjectProperty]
    _axioms: AxiomsHint

    def append_relationship(
        self,
        typedef: ReferenceHint,
        reference: ReferenceHint,
        *,
        axioms: Iterable[ObjectProperty | LiteralProperty] | None = None,
    ) -> Self:
        """Append a relationship."""
        typedef = _ensure_ref(typedef)
        reference = _ensure_ref(reference)
        self.relationships[typedef].append(reference)
        self._annotate_axioms(typedef, reference, axioms)
        return self

    def _annotate_axioms(
        self, p: Reference, o: Reference, axioms: Iterable[ObjectProperty | LiteralProperty] | None
    ) -> None:
        if axioms is None:
            return
        for axiom in axioms:
            self._annotate_axiom(p, o, axiom)

    def _annotate_axiom(
        self, p: Reference, o: Reference, axiom: ObjectProperty | LiteralProperty
    ) -> None:
        match axiom:
            case ObjectProperty(predicate, object):
                self._axioms[p, o].append((predicate, object))
            case LiteralProperty(predicate, literal):
                self._axioms[p, o].append((predicate, literal))

    def append_equivalent(
        self,
        reference: ReferenceHint,
    ) -> Self:
        """Append an equivalent class axiom."""
        reference = _ensure_ref(reference)
        self.append_relationship(v.equivalent_class, reference)
        return self

    def append_xref(
        self,
        reference: ReferenceHint,
        *,
        mapping_justification: Reference | None = None,
        confidence: float | None = None,
        contributor: Reference | None = None,
    ) -> Self:
        """Append an xref."""
        reference = _ensure_ref(reference)
        self.xrefs.append(reference)
        axioms = self._prepare_mapping_axioms(
            mapping_justification=mapping_justification,
            confidence=confidence,
            contributor=contributor,
        )
        self._annotate_axioms(v.has_dbxref, reference, axioms)
        return self

    def _prepare_mapping_axioms(
        self,
        *,
        mapping_justification: Reference | None = None,
        confidence: float | None = None,
        contributor: Reference | None = None,
    ) -> Iterable[ObjectProperty | LiteralProperty]:
        if mapping_justification is not None:
            yield ObjectProperty(v.mapping_has_justification, mapping_justification)
        if contributor is not None:
            yield ObjectProperty(v.has_contributor, contributor)
        if confidence is not None:
            yield LiteralProperty.float(v.mapping_has_confidence, confidence)

    def append_parent(self, reference: ReferenceHint) -> Self:
        """Add a parent to this entity."""
        reference = _ensure_ref(reference)
        if reference not in self.parents:
            self.parents.append(reference)
        return self

    def append_provenance(self, reference: ReferenceHint) -> Self:
        """Add a provenance reference."""
        self.provenance.append(_ensure_ref(reference))
        return self

    def append_intersection_of(
        self, /, reference: ReferenceHint | ObjectProperty, r2: ReferenceHint | None = None
    ) -> Self:
        """Append an intersection of."""
        if r2 is not None:
            if isinstance(reference, ObjectProperty):
                raise TypeError
            self.intersection_of.append(ObjectProperty(_ensure_ref(reference), _ensure_ref(r2)))
        elif isinstance(reference, ObjectProperty):
            self.intersection_of.append(reference)
        else:
            self.intersection_of.append(_ensure_ref(reference))
        return self

    def _iterate_intersection_of_obo(self, *, ontology_prefix: str) -> Iterable[str]:
        for element in self.intersection_of:
            match element:
                case Reference():
                    end = reference_escape(
                        element, ontology_prefix=ontology_prefix, add_name_comment=True
                    )
                case ObjectProperty(predicate, object):
                    end = multi_reference_escape(
                        [predicate, object], ontology_prefix=ontology_prefix, add_name_comment=True
                    )
                case _:
                    raise TypeError
            yield f"intersection_of: {end}"

    def _iterate_xref_obo(self, *, ontology_prefix) -> Iterable[str]:
        for xref in sorted(self.xrefs):
            xref_yv = f"xref: {reference_escape(xref, ontology_prefix=ontology_prefix, add_name_comment=False)}"
            xref_yv += _get_obo_trailing_modifiers(
                v.has_dbxref, xref, self._axioms, ontology_prefix=ontology_prefix
            )
            if xref.name:
                xref_yv += f" ! {xref.name}"
            yield xref_yv


ReferenceHint: TypeAlias = Reference | Referenced | tuple[str, str] | str


def _ensure_ref(
    reference: ReferenceHint,
    *,
    ontology_prefix: str | None = None,
) -> Reference:
    if isinstance(reference, Referenced):
        return reference.reference
    if isinstance(reference, tuple):
        return Reference(prefix=reference[0], identifier=reference[1])
    if isinstance(reference, Reference):
        return reference
    if ":" not in reference:
        if not ontology_prefix:
            raise ValueError(f"can't parse reference: {reference}")
        return default_reference(ontology_prefix, reference)
    _rv = Reference.from_curie_or_uri(reference, strict=True, ontology_prefix=ontology_prefix)
    if _rv is None:
        raise ValueError(f"[{ontology_prefix}] unable to parse {reference}")
    return _rv


def _chain_tag(tag: str, chain: list[Reference] | None, ontology_prefix: str) -> Iterable[str]:
    if chain:
        yield f"{tag}: {multi_reference_escape(chain, ontology_prefix=ontology_prefix, add_name_comment=True)}"


def _iterate_obo_relations(
    relations: Mapping[Reference, Sequence[Reference | OBOLiteral]],
    annotations: AxiomsHint,
    *,
    ontology_prefix: str,
) -> Iterable[str]:
    """Iterate over relations/property values for OBO."""
    for predicate, values in relations.items():
        # TODO typedef warning: ``_typedef_warn(prefix=ontology_prefix, predicate=predicate, typedefs=typedefs)``
        pc = reference_escape(predicate, ontology_prefix=ontology_prefix)
        start = f"{pc} "
        for value in values:
            match value:
                case OBOLiteral(dd, datatype):
                    # TODO how to clean/escape value?
                    end = f'"{dd}" {datatype.preferred_curie}'
                    name = None
                case curies.Reference():  # it's a reference
                    end = reference_escape(value, ontology_prefix=ontology_prefix)
                    name = value.name
                case _:
                    raise TypeError(f"got unexpected value: {values}")
            end += _get_obo_trailing_modifiers(
                predicate, value, annotations, ontology_prefix=ontology_prefix
            )
            if predicate.name and name:
                end += f" ! {predicate.name} {name}"
            yield start + end


def _get_obo_trailing_modifiers(
    p: Reference, o: Reference | OBOLiteral, axioms: AxiomsHint, *, ontology_prefix: str
) -> str:
    """Lookup then format a sequence of axioms for OBO trailing modifiers."""
    if annotations := axioms.get((p, o), []):
        return _format_obo_trailing_modifiers(annotations, ontology_prefix=ontology_prefix)
    return ""


def _format_obo_trailing_modifiers(
    annotations: Sequence[tuple[Reference, Reference | OBOLiteral]], *, ontology_prefix: str
) -> str:
    """Format a sequence of axioms for OBO trailing modifiers.

    :param annotations: A list of annnotations
    :param ontology_prefix: The ontology prefix
    :return: The trailing modifiers string

    See https://owlcollab.github.io/oboformat/doc/GO.format.obo-1_4.html#S.1.4
    trailing modifiers can be both axioms and some other implementation-specific
    things, so split up the place where axioms are put in here.
    """
    modifiers: list[tuple[str, str]] = []
    for predicate, part in annotations:
        ap_str = reference_escape(predicate, ontology_prefix=ontology_prefix)
        match part:
            case OBOLiteral(dd, _datatype):
                ao_str = str(dd)
            case _:  # it's a reference
                ao_str = reference_escape(part, ontology_prefix=ontology_prefix)
        modifiers.append((ap_str, ao_str))
    inner = ", ".join(f"{key}={value}" for key, value in sorted(modifiers))
    return " {" + inner + "}"
