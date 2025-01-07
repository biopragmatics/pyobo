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
    "ReferenceHint",
    "Stanza",
]


class Annotation(NamedTuple):
    """A tuple representing a predicate-object pair."""

    predicate: Reference
    value: Reference | OBOLiteral

    @classmethod
    def float(cls, predicate: Reference, value: float) -> Self:
        """Return a literal property for a float."""
        return cls(predicate, OBOLiteral(str(value), Reference(prefix="xsd", identifier="float")))


def _property_resolve(
    p: Reference | Referenced, o: Reference | Referenced | OBOLiteral
) -> Annotation:
    if isinstance(p, Referenced):
        p = p.reference
    if isinstance(o, Referenced):
        o = o.reference
    return Annotation(p, o)


PropertiesHint: TypeAlias = dict[Reference, list[Reference | OBOLiteral]]
RelationsHint: TypeAlias = dict[Reference, list[Reference]]
AxiomsHint: TypeAlias = dict[Annotation, list[Annotation]]
IntersectionOfHint: TypeAlias = list[Reference | Annotation]
UnionOfHint: TypeAlias = list[Reference]


class Stanza:
    """A high-level class for stanzas."""

    relationships: RelationsHint
    properties: PropertiesHint
    xrefs: list[Reference]
    parents: list[Reference]
    provenance: list[Reference]
    intersection_of: IntersectionOfHint
    equivalent_to: list[Reference]
    union_of: UnionOfHint
    _axioms: AxiomsHint

    def append_relationship(
        self,
        typedef: ReferenceHint,
        reference: ReferenceHint,
        *,
        axioms: Iterable[Annotation] | None = None,
    ) -> Self:
        """Append a relationship."""
        typedef = _ensure_ref(typedef)
        reference = _ensure_ref(reference)
        self.relationships[typedef].append(reference)
        self._annotate_axioms(typedef, reference, axioms)
        return self

    def _annotate_axioms(
        self, p: Reference, o: Reference, axioms: Iterable[Annotation] | None
    ) -> None:
        if axioms is None:
            return
        for axiom in axioms:
            self._annotate_axiom(p, o, axiom)

    def _annotate_axiom(self, p: Reference, o: Reference | OBOLiteral, axiom: Annotation) -> None:
        self._axioms[_property_resolve(p, o)].append(axiom)

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
    ) -> Iterable[Annotation]:
        if mapping_justification is not None:
            yield Annotation(v.mapping_has_justification, mapping_justification)
        if contributor is not None:
            yield Annotation(v.has_contributor, contributor)
        if confidence is not None:
            yield Annotation.float(v.mapping_has_confidence, confidence)

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
        self, /, reference: ReferenceHint | Annotation, r2: ReferenceHint | None = None
    ) -> Self:
        """Append an intersection of."""
        if r2 is not None:
            if isinstance(reference, Annotation):
                raise TypeError
            self.intersection_of.append(Annotation(_ensure_ref(reference), _ensure_ref(r2)))
        elif isinstance(reference, Annotation):
            self.intersection_of.append(reference)
        else:
            self.intersection_of.append(_ensure_ref(reference))
        return self

    def append_union_of(self, reference: ReferenceHint) -> Self:
        """Append to the "union of" list."""
        self.union_of.append(_ensure_ref(reference))
        return self

    def append_equivalent_to(self, reference: ReferenceHint) -> Self:
        """Append to the "equivalent to" list."""
        self.equivalent_to.append(_ensure_ref(reference))
        return self

    def _iterate_intersection_of_obo(self, *, ontology_prefix: str) -> Iterable[str]:
        for element in self.intersection_of:
            match element:
                case Reference():
                    end = reference_escape(
                        element, ontology_prefix=ontology_prefix, add_name_comment=True
                    )
                case Annotation(predicate, object):
                    match object:
                        case Reference():
                            end = multi_reference_escape(
                                [predicate, object],
                                ontology_prefix=ontology_prefix,
                                add_name_comment=True,
                            )
                        case OBOLiteral():
                            raise NotImplementedError
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

    def _get_axioms(
        self, p: Reference | Referenced, o: Reference | Referenced | OBOLiteral
    ) -> list[Annotation]:
        return self._axioms.get(_property_resolve(p, o), [])

    def _get_axiom(
        self, p: Reference, o: Reference | OBOLiteral, ap: Reference
    ) -> Reference | OBOLiteral | None:
        ap_norm = _ensure_ref(ap)
        for axiom in self._get_axioms(p, o):
            if axiom.predicate.pair == ap_norm.pair:
                return axiom.value
        return None

    def append_property(self, prop: Annotation) -> Self:
        """Annotate a property."""
        self.properties[prop.predicate].append(prop.value)
        return self

    def annotate_literal(
        self, prop: ReferenceHint, value: str, datatype: Reference | None = None
    ) -> Self:
        """Append an object annotation."""
        prop = _ensure_ref(prop)
        self.properties[prop].append(
            OBOLiteral(value, datatype or Reference(prefix="xsd", identifier="string"))
        )
        return self

    def annotate_boolean(self, prop: ReferenceHint, value: bool) -> Self:
        """Append an object annotation."""
        return self.annotate_literal(
            prop, str(value).lower(), Reference(prefix="xsd", identifier="boolean")
        )

    def annotate_integer(self, prop: ReferenceHint, value: int | str) -> Self:
        """Append an object annotation."""
        return self.annotate_literal(
            prop, str(int(value)), Reference(prefix="xsd", identifier="integer")
        )

    def annotate_year(self, prop: ReferenceHint, value: int | str) -> Self:
        """Append a year annotation."""
        return self.annotate_literal(
            prop, str(int(value)), Reference(prefix="xsd", identifier="gYear")
        )

    def _iterate_obo_properties(self, *, ontology_prefix: str) -> Iterable[str]:
        for line in _iterate_obo_relations(
            # the type checker seems to be a bit confused, this is an okay typing since we're
            # passing a more explicit version. The issue is that list is used for the typing,
            # which means it can't narrow properly
            self.properties,  # type:ignore
            self._axioms,
            ontology_prefix=ontology_prefix,
        ):
            yield f"property_value: {line}"

    def _iterate_obo_relations(self, *, ontology_prefix: str) -> Iterable[str]:
        for line in _iterate_obo_relations(
            # the type checker seems to be a bit confused, this is an okay typing since we're
            # passing a more explicit version. The issue is that list is used for the typing,
            # which means it can't narrow properly
            self.relationships,  # type:ignore
            self._axioms,
            ontology_prefix=ontology_prefix,
        ):
            yield f"relationship: {line}"


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
    if annotations := axioms.get(_property_resolve(p, o), []):
        return _format_obo_trailing_modifiers(annotations, ontology_prefix=ontology_prefix)
    return ""


def _format_obo_trailing_modifiers(
    annotations: Sequence[Annotation], *, ontology_prefix: str
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
    for prop in annotations:
        left = reference_escape(prop.predicate, ontology_prefix=ontology_prefix)
        match prop.value:
            case Reference():
                right = reference_escape(prop.value, ontology_prefix=ontology_prefix)
            case OBOLiteral(value, _datatype):
                right = value
        modifiers.append((left, right))
    inner = ", ".join(f"{key}={value}" for key, value in sorted(modifiers))
    return " {" + inner + "}"
