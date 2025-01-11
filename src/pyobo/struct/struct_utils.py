"""Utiltites on top of the reference."""

from __future__ import annotations

import itertools as itt
import logging
from collections.abc import Iterable, Mapping, Sequence
from typing import TYPE_CHECKING, Literal, NamedTuple, TypeAlias, overload

import curies
from curies import ReferenceTuple
from curies.vocabulary import SynonymScope
from pydantic import BaseModel, ConfigDict
from typing_extensions import Self

from . import vocabulary as v
from .reference import (
    OBOLiteral,
    Reference,
    Referenced,
    comma_separate_references,
    default_reference,
    get_preferred_curie,
    multi_reference_escape,
    reference_escape,
    unspecified_matching,
)
from .utils import obo_escape_slim

if TYPE_CHECKING:
    from pyobo.struct.struct import Synonym, TypeDef

__all__ = [
    "AxiomsHint",
    "ReferenceHint",
    "Stanza",
]

logger = logging.getLogger(__name__)


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
# note that an intersection is not valid in ROBOT with a literal, even though this _might_ make sense.
IntersectionOfHint: TypeAlias = list[Reference | tuple[Reference, Reference]]
UnionOfHint: TypeAlias = list[Reference]


class Stanza:
    """A high-level class for stanzas."""

    reference: Reference
    relationships: RelationsHint
    properties: PropertiesHint
    xrefs: list[Reference]
    parents: list[Reference]
    intersection_of: IntersectionOfHint
    equivalent_to: list[Reference]
    union_of: UnionOfHint
    subsets: list[Reference]
    disjoint_from: list[Reference]
    synonyms: list[Synonym]

    _axioms: AxiomsHint

    #: An annotation for obsolescence. By default, is None, but this means that it is not obsolete.
    is_obsolete: bool | None

    #: A description of the entity
    definition: str | None = None

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

    def append_intersection_of(
        self,
        /,
        reference: ReferenceHint | tuple[ReferenceHint, ReferenceHint],
        r2: ReferenceHint | None = None,
    ) -> Self:
        """Append an intersection of."""
        if r2 is not None:
            if isinstance(reference, tuple):
                raise TypeError
            self.intersection_of.append((_ensure_ref(reference), _ensure_ref(r2)))
        elif isinstance(reference, tuple):
            self.intersection_of.append((_ensure_ref(reference[0]), _ensure_ref(reference[1])))
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
                case (predicate, object):
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

    def _iterate_obo_properties(
        self,
        *,
        ontology_prefix: str,
        skip_predicates: Iterable[Reference] | None = None,
        typedefs: Mapping[ReferenceTuple, TypeDef],
    ) -> Iterable[str]:
        if skip_predicates:
            # set for faster membership testing
            skip_predicates = set(skip_predicates)
        for line in _iterate_obo_relations(
            # the type checker seems to be a bit confused, this is an okay typing since we're
            # passing a more explicit version. The issue is that list is used for the typing,
            # which means it can't narrow properly
            self.properties,  # type:ignore
            self._axioms,
            ontology_prefix=ontology_prefix,
            skip_predicate_objects=skip_predicates,
            typedefs=typedefs,
        ):
            yield f"property_value: {line}"

    def _iterate_obo_relations(
        self, *, ontology_prefix: str, typedefs: Mapping[ReferenceTuple, TypeDef]
    ) -> Iterable[str]:
        for line in _iterate_obo_relations(
            # the type checker seems to be a bit confused, this is an okay typing since we're
            # passing a more explicit version. The issue is that list is used for the typing,
            # which means it can't narrow properly
            self.relationships,  # type:ignore
            self._axioms,
            ontology_prefix=ontology_prefix,
            typedefs=typedefs,
        ):
            yield f"relationship: {line}"

    def append_subset(self, subset: ReferenceHint) -> Self:
        """Add a subset."""
        self.subsets.append(_ensure_ref(subset))
        return self

    def append_disjoint_from(self, reference: ReferenceHint) -> Self:
        """Add a disjoint from."""
        self.disjoint_from.append(_ensure_ref(reference))
        return self

    def annotate_object(
        self,
        typedef: ReferenceHint,
        value: ReferenceHint,
        *,
        axioms: Iterable[Annotation] | None = None,
    ) -> Self:
        """Append an object annotation."""
        typedef = _ensure_ref(typedef)
        value = _ensure_ref(value)
        self.properties[typedef].append(value)
        self._annotate_axioms(typedef, value, axioms)
        return self

    def get_replaced_by(self) -> list[Reference]:
        """Get all replaced by."""
        return self.get_property_objects(v.term_replaced_by)

    def append_replaced_by(self, reference: Reference) -> Self:
        """Add a replaced by property."""
        return self.annotate_object(v.term_replaced_by, reference)

    def iterate_relations(self) -> Iterable[tuple[Reference, Reference]]:
        """Iterate over pairs of typedefs and targets."""
        for typedef, targets in sorted(self.relationships.items()):
            for target in sorted(targets):
                yield typedef, target

    def get_relationships(self, typedef: ReferenceHint) -> list[Reference]:
        """Get relationships from the given type."""
        return self.relationships.get(_ensure_ref(typedef), [])

    def get_relationship(self, typedef: ReferenceHint) -> Reference | None:
        """Get a single relationship of the given type."""
        r = self.get_relationships(typedef)
        if not r:
            return None
        if len(r) > 1:
            raise ValueError
        return r[0]

    def iterate_relation_targets(self, typedef: ReferenceHint) -> list[Reference]:
        """Iterate over pairs of typedefs and targets."""
        return sorted(self.relationships.get(_ensure_ref(typedef), []))

    def get_property_annotations(self) -> list[Annotation]:
        """Iterate over pairs of property and values."""
        return [
            Annotation(prop, value)
            for prop, values in sorted(self.properties.items())
            for value in values
        ]

    def get_property_values(self, typedef: ReferenceHint) -> list[Reference | OBOLiteral]:
        """Iterate over references or values."""
        return sorted(self.properties.get(_ensure_ref(typedef), []))

    def get_property_objects(self, prop: ReferenceHint) -> list[Reference]:
        """Get properties from the given key."""
        return [
            reference
            for reference in self.properties.get(_ensure_ref(prop), [])
            if isinstance(reference, curies.Reference)
        ]

    def append_synonym(
        self,
        synonym: str | Synonym,
        *,
        type: Reference | Referenced | None = None,
        specificity: SynonymScope | None = None,
        provenance: list[Reference] | None = None,
    ) -> Self:
        """Add a synonym."""
        if isinstance(type, Referenced):
            type = type.reference
        if isinstance(synonym, str):
            from pyobo.struct.struct import Synonym

            synonym = Synonym(
                synonym,
                type=type,
                specificity=specificity,
                provenance=provenance or [],
            )
        self.synonyms.append(synonym)
        return self

    def append_alt(self, alt: Reference) -> Self:
        """Add an alternative identifier."""
        return self.annotate_object(v.alternative_term, alt)

    def append_see_also(self, reference: ReferenceHint) -> Self:
        """Add a see also property."""
        _reference = _ensure_ref(reference)
        return self.annotate_object(v.see_also, _reference)

    def append_comment(self, value: str) -> Self:
        """Add a comment property."""
        return self.annotate_literal(v.comment, value)

    @property
    def alt_ids(self) -> Sequence[Reference]:
        """Get alternative terms."""
        return tuple(self.get_property_objects(v.alternative_term))

    def get_edges(self) -> list[tuple[Reference, Reference]]:
        """Get edges."""
        return list(self._iter_edges())

    def _iter_edges(self) -> Iterable[tuple[Reference, Reference]]:
        yield from self.iterate_relations()
        for parent in itt.chain(self.parents, self.union_of):
            yield v.is_a, parent
        for subset in self.subsets:
            yield v.in_subset, subset
        for k, values in self.properties.items():
            for value in values:
                if isinstance(value, Reference):
                    yield k, value
        for intersection_of in self.intersection_of:
            match intersection_of:
                case Reference():
                    yield v.is_a, intersection_of
                case (predicate, target):
                    yield predicate, target
        # TODO disjoint_from
        yield from self.get_mappings(include_xrefs=True, add_context=False)

    # docstr-coverage:excused `overload`
    @overload
    def get_mappings(
        self, *, include_xrefs: bool = ..., add_context: Literal[True] = True
    ) -> list[tuple[Reference, Reference, MappingContext]]: ...

    # docstr-coverage:excused `overload`
    @overload
    def get_mappings(
        self, *, include_xrefs: bool = ..., add_context: Literal[False] = False
    ) -> list[tuple[Reference, Reference]]: ...

    def get_mappings(
        self, *, include_xrefs: bool = True, add_context: bool = False
    ) -> list[tuple[Reference, Reference]] | list[tuple[Reference, Reference, MappingContext]]:
        """Get mappings with preferred curies."""
        rows = []
        for predicate in v.extended_match_typedefs:
            for xref_reference in itt.chain(
                self.get_property_objects(predicate), self.get_relationships(predicate)
            ):
                rows.append((predicate, xref_reference))
        if include_xrefs:
            for xref_reference in self.xrefs:
                rows.append((v.has_dbxref, xref_reference))
        for equivalent_to in self.equivalent_to:
            rows.append((v.equivalent_class, equivalent_to))
        rv = sorted(set(rows))
        if not add_context:
            return rv
        return [(k, v, self._get_mapping_context(k, v)) for k, v in rv]

    def _get_object_axiom_target(
        self, p: Reference, o: Reference | OBOLiteral, ap: Reference
    ) -> Reference | None:
        match self._get_axiom(p, o, ap):
            case OBOLiteral():
                raise TypeError
            case Reference() as target:
                return target
            case None:
                return None
            case _:
                raise TypeError

    def _get_str_axiom_target(
        self, p: Reference, o: Reference | OBOLiteral, ap: Reference
    ) -> str | None:
        match self._get_axiom(p, o, ap):
            case OBOLiteral(value, _):
                return value
            case Reference():
                raise TypeError
            case None:
                return None
            case _:
                raise TypeError

    def _get_mapping_context(self, p: Reference, o: Reference) -> MappingContext:
        return MappingContext(
            justification=self._get_object_axiom_target(p, o, v.mapping_has_justification)
            or unspecified_matching,
            contributor=self._get_object_axiom_target(p, o, v.has_contributor),
            confidence=self._get_str_axiom_target(p, o, v.mapping_has_confidence),
        )

    def _definition_fp(self) -> str:
        definition = obo_escape_slim(self.definition) if self.definition else ""
        return f'"{definition}" [{comma_separate_references(self._get_definition_provenance())}]'

    def _get_definition_provenance(self) -> list[Reference]:
        if not self.definition:
            return []
        return [
            ax.value
            for ax in self._get_axioms(v.has_description, OBOLiteral.string(self.definition))
            if ax.predicate.pair == v.has_dbxref.pair and isinstance(ax.value, Reference)
        ]

    @property
    def provenance(self) -> Sequence[Reference]:
        """Get definition provenance."""
        # return as a tuple to make sure nobody is appending on it
        return (
            *self._get_definition_provenance(),
            *self.get_property_objects(v.has_citation),
        )

    def append_provenance(self, reference: ReferenceHint) -> Self:
        """Add a reference to this term's definition."""
        if not self.definition:
            raise ValueError("can not append definition provenance if no definition is set")
        self._annotate_axiom(
            v.has_description,
            OBOLiteral.string(self.definition),
            Annotation(v.has_dbxref, _ensure_ref(reference)),
        )
        return self

    def append_citation(self, reference: Reference) -> Self:
        """Append a citation."""
        return self.annotate_object(v.has_citation, reference)


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


def _chain_tag(
    tag: str, chains: list[list[Reference]] | None, ontology_prefix: str
) -> Iterable[str]:
    for chain in chains or []:
        yield f"{tag}: {multi_reference_escape(chain, ontology_prefix=ontology_prefix, add_name_comment=True)}"


def _tag_property_targets(
    tag: str, stanza: Stanza, prod: ReferenceHint, *, ontology_prefix: str
) -> Iterable[str]:
    for x in stanza.get_property_values(_ensure_ref(prod)):
        if isinstance(x, Reference):
            yield f"{tag}: {reference_escape(x, ontology_prefix=ontology_prefix, add_name_comment=True)}"


def _iterate_obo_relations(
    relations: Mapping[Reference, Sequence[Reference | OBOLiteral]],
    annotations: AxiomsHint,
    *,
    ontology_prefix: str,
    skip_predicate_objects: Iterable[Reference] | None = None,
    typedefs: Mapping[ReferenceTuple, TypeDef],
) -> Iterable[str]:
    """Iterate over relations/property values for OBO."""
    if skip_predicate_objects is None:
        skip_predicate_objects = set()
    else:
        skip_predicate_objects = set(skip_predicate_objects)
    for predicate, values in relations.items():
        _typedef_warn(prefix=ontology_prefix, predicate=predicate, typedefs=typedefs)
        pc = reference_escape(predicate, ontology_prefix=ontology_prefix)
        start = f"{pc} "
        for value in values:
            match value:
                case OBOLiteral(dd, datatype):
                    # TODO how to clean/escape value?
                    end = f'"{dd}" {get_preferred_curie(datatype)}'
                    name = None
                case curies.Reference():  # it's a reference
                    if predicate in skip_predicate_objects:
                        # this allows us to special case out iterating over
                        # ones that are configured with their own tags
                        continue
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


#: A set of warnings, used to make sure we don't show the same one over and over
_TYPEDEF_WARNINGS: set[tuple[str, Reference]] = set()


def _typedef_warn(
    prefix: str, predicate: Reference, typedefs: Mapping[ReferenceTuple, TypeDef]
) -> None:
    from pyobo.struct.typedef import default_typedefs

    if predicate.pair in default_typedefs or predicate.pair in typedefs:
        return None
    key = prefix, predicate
    if key not in _TYPEDEF_WARNINGS:
        _TYPEDEF_WARNINGS.add(key)
        if predicate.prefix == "obo":
            # Throw our hands up in the air. By using `obo` as the prefix,
            # we already threw using "real" definitions out the window
            logger.warning(
                f"[{prefix}] predicate with OBO prefix not defined: {predicate.curie}."
                f"\n\tThis might be because you used an unqualified prefix in an OBO file, "
                f"which automatically gets an OBO prefix."
            )
        else:
            logger.warning(f"[{prefix}] typedef not defined: {predicate.curie}")


class MappingContext(BaseModel):
    """Context for a mapping, corresponding to SSSOM."""

    justification: Reference = unspecified_matching
    contributor: Reference | None = None
    confidence: float | None = None

    model_config = ConfigDict(
        frozen=True,  # Makes the model immutable and hashable
    )
