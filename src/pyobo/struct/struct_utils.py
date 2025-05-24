"""Utiltites on top of the reference."""

from __future__ import annotations

import datetime
import itertools as itt
import logging
from abc import ABC, abstractmethod
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from typing import TYPE_CHECKING, Literal, NamedTuple, TypeAlias, overload

import curies
from curies import ReferenceTuple
from curies import vocabulary as _v
from curies.vocabulary import SynonymScope
from pydantic import BaseModel, ConfigDict
from ssslm import LiteralMapping
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
    reference_or_literal_to_str,
    unspecified_matching,
)
from .utils import obo_escape_slim
from ..identifier_utils import (
    NotCURIEError,
    ParseError,
    _is_valid_identifier,
    _parse_str_or_curie_or_uri_helper,
)

if TYPE_CHECKING:
    from pyobo.struct.struct import Synonym, TypeDef

__all__ = [
    "AnnotationsDict",
    "HasReferencesMixin",
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
        return cls(predicate, OBOLiteral.float(value))

    @staticmethod
    def _sort_key(x: Annotation):
        return x.predicate, _reference_or_literal_key(x.value)


def _property_resolve(p: ReferenceHint, o: Reference | Referenced | OBOLiteral) -> Annotation:
    p = _ensure_ref(p)
    if isinstance(o, Referenced):
        o = o.reference
    return Annotation(p, o)


PropertiesHint: TypeAlias = dict[Reference, list[Reference | OBOLiteral]]
RelationsHint: TypeAlias = dict[Reference, list[Reference]]
AnnotationsDict: TypeAlias = dict[Annotation, list[Annotation]]
# note that an intersection is not valid in ROBOT with a literal, even though this _might_ make sense.
IntersectionOfHint: TypeAlias = list[Reference | tuple[Reference, Reference]]
UnionOfHint: TypeAlias = list[Reference]

StanzaType: TypeAlias = Literal["Term", "Instance", "TypeDef"]

stanza_type_to_prop: dict[StanzaType, Reference] = {
    "Term": v.is_a,
    "Instance": v.rdf_type,
    "TypeDef": v.subproperty_of,
}

stanza_type_to_eq_prop: dict[StanzaType, Reference] = {
    "Term": v.equivalent_class,
    "Instance": v.owl_same_as,
    "TypeDef": v.equivalent_property,
}


class HasReferencesMixin(ABC):
    """A class that can report on the references it contains."""

    def _get_prefixes(self) -> set[str]:
        return set(self._get_references())

    @abstractmethod
    def _get_references(self) -> dict[str, set[Reference]]:
        raise NotImplementedError


class Stanza(Referenced, HasReferencesMixin):
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

    type: StanzaType

    _axioms: AnnotationsDict

    #: An annotation for obsolescence. By default, is None, but this means that it is not obsolete.
    is_obsolete: bool | None

    #: A description of the entity
    definition: str | None = None

    @staticmethod
    def _reference(
        reference: Reference, ontology_prefix: str, add_name_comment: bool = False
    ) -> str:
        return reference_escape(
            reference, ontology_prefix=ontology_prefix, add_name_comment=add_name_comment
        )

    def _get_prefixes(self) -> set[str]:
        return set(self._get_references())

    def _get_references(self) -> dict[str, set[Reference]]:
        """Get all prefixes used by the typedef."""
        rv: defaultdict[str, set[Reference]] = defaultdict(set)

        def _add(r: Reference) -> None:
            rv[r.prefix].add(r)

        _add(self.reference)

        for synonym in self.synonyms:
            for prefix, references in synonym._get_references().items():
                rv[prefix].update(references)

        if self.xrefs:
            # xrefs themselves added in the chain below
            _add(v.has_dbxref)

        for predicate, values in self.properties.items():
            _add(predicate)
            for value in values:
                if isinstance(value, Reference):
                    _add(value)
                elif isinstance(value, OBOLiteral):
                    _add(v._c(value.datatype))
        for parent in itt.chain(
            self.parents,
            self.union_of,
            self.equivalent_to,
            self.disjoint_from,
            self.subsets,
            self.xrefs,
        ):
            _add(parent)
        for intersection_of in self.intersection_of:
            match intersection_of:
                case Reference():
                    _add(intersection_of)
                case (intersection_predicate, intersection_value):
                    _add(intersection_predicate)
                    _add(intersection_value)

        for rel_predicate, rel_values in self.relationships.items():
            _add(rel_predicate)
            for r in rel_values:
                _add(r)
        for p_o, annotations_ in self._axioms.items():
            _add(p_o.predicate)
            if isinstance(p_o.value, Reference):
                _add(p_o.value)
            for prefix, references in _get_references_from_annotations(annotations_).items():
                rv[prefix].update(references)
        return rv

    def get_literal_mappings(self) -> list[LiteralMapping]:
        """Get synonym objects for this term, including one for its label."""
        rv = [_convert_synoynym(self, synonym) for synonym in self.synonyms]
        if self.reference.name:
            rv.append(_get_stanza_name_synonym(self))
        return rv

    def append_relationship(
        self,
        typedef: ReferenceHint,
        reference: ReferenceHint,
        *,
        annotations: Iterable[Annotation] | None = None,
    ) -> Self:
        """Append a relationship."""
        typedef = _ensure_ref(typedef)
        reference = _ensure_ref(reference)
        self.relationships[typedef].append(reference)
        self._extend_annotations(typedef, reference, annotations)
        return self

    def _extend_annotations(
        self, p: Reference, o: Reference | OBOLiteral, annotations: Iterable[Annotation] | None
    ) -> None:
        if annotations is None:
            return
        for annotation in annotations:
            self._append_annotation(p, o, annotation)

    def _append_annotation(
        self, p: ReferenceHint, o: Reference | OBOLiteral, annotation: Annotation
    ) -> None:
        self._axioms[_property_resolve(p, o)].append(annotation)

    # TODO check different usages of this

    def append_equivalent(
        self,
        reference: ReferenceHint,
        *,
        annotations: Iterable[Annotation] | None = None,
    ) -> Self:
        """Append an equivalent class axiom."""
        return self.append_relationship(
            stanza_type_to_eq_prop[self.type], reference, annotations=annotations
        )

    def append_equivalent_to(
        self, reference: ReferenceHint, *, annotations: Iterable[Annotation] | None = None
    ) -> Self:
        """Append to the "equivalent to" list."""
        reference = _ensure_ref(reference)
        self.equivalent_to.append(reference)
        self._extend_annotations(stanza_type_to_eq_prop[self.type], reference, annotations)
        return self

    def append_xref(
        self,
        reference: ReferenceHint,
        *,
        mapping_justification: Reference | None = None,
        confidence: float | None = None,
        contributor: Reference | None = None,
        annotations: list[Annotation] | None = None,
    ) -> Self:
        """Append an xref."""
        reference = _ensure_ref(reference)
        self.xrefs.append(reference)
        if annotations is None:
            annotations = []
        annotations.extend(
            self._prepare_mapping_annotations(
                mapping_justification=mapping_justification,
                confidence=confidence,
                contributor=contributor,
            )
        )
        self._extend_annotations(v.has_dbxref, reference, annotations)
        return self

    def _prepare_mapping_annotations(
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

    def append_parent(
        self,
        reference: ReferenceHint,
        *,
        annotations: Iterable[Annotation] | None = None,
    ) -> Self:
        """Add a parent to this entity."""
        reference = _ensure_ref(reference)
        if reference not in self.parents:
            self.parents.append(reference)
        self._extend_annotations(stanza_type_to_prop[self.type], reference, annotations)
        return self

    def append_intersection_of(
        self,
        /,
        reference: ReferenceHint | tuple[ReferenceHint, ReferenceHint],
        r2: ReferenceHint | None = None,
        *,
        annotations: Iterable[Annotation] | None = None,
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

    def _iterate_intersection_of_obo(self, *, ontology_prefix: str) -> Iterable[str]:
        for element in sorted(self.intersection_of, key=self._intersection_of_key):
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

    @staticmethod
    def _intersection_of_key(io: Reference | tuple[Reference, Reference]):
        if isinstance(io, Reference):
            return 0, io
        else:
            return 1, io

    def _iterate_xref_obo(self, *, ontology_prefix) -> Iterable[str]:
        for xref in sorted(self.xrefs):
            xref_yv = f"xref: {reference_escape(xref, ontology_prefix=ontology_prefix, add_name_comment=False)}"
            xref_yv += _get_obo_trailing_modifiers(
                v.has_dbxref, xref, self._axioms, ontology_prefix=ontology_prefix
            )
            if xref.name:
                xref_yv += f" ! {xref.name}"
            yield xref_yv

    def _get_annotations(
        self, p: ReferenceHint, o: Reference | Referenced | OBOLiteral | str
    ) -> list[Annotation]:
        if isinstance(o, str):
            o = OBOLiteral.string(o)
        return self._axioms.get(_property_resolve(p, o), [])

    def _get_annotation(
        self, p: ReferenceHint, o: Reference | OBOLiteral, ap: Reference
    ) -> Reference | OBOLiteral | None:
        ap_norm = _ensure_ref(ap)
        for annotation in self._get_annotations(p, o):
            if annotation.predicate.pair == ap_norm.pair:
                return annotation.value
        return None

    def append_property(
        self, prop: Annotation, *, annotations: Iterable[Annotation] | None = None
    ) -> Self:
        """Annotate a property."""
        self.properties[prop.predicate].append(prop.value)
        self._extend_annotations(prop.predicate, prop.value, annotations)
        return self

    def annotate_literal(
        self,
        prop: ReferenceHint,
        value: OBOLiteral,
        *,
        annotations: Iterable[Annotation] | None = None,
    ) -> Self:
        """Append an object annotation."""
        prop = _ensure_ref(prop)
        self.properties[prop].append(value)
        self._extend_annotations(prop, value, annotations)
        return self

    def annotate_string(
        self,
        prop: ReferenceHint,
        value: str,
        *,
        annotations: Iterable[Annotation] | None = None,
        language: str | None = None,
    ) -> Self:
        """Append an object annotation."""
        return self.annotate_literal(
            prop, OBOLiteral.string(value, language=language), annotations=annotations
        )

    def annotate_boolean(
        self,
        prop: ReferenceHint,
        value: bool,
        *,
        annotations: Iterable[Annotation] | None = None,
    ) -> Self:
        """Append an object annotation."""
        return self.annotate_literal(prop, OBOLiteral.boolean(value), annotations=annotations)

    def annotate_integer(
        self,
        prop: ReferenceHint,
        value: int | str,
        *,
        annotations: Iterable[Annotation] | None = None,
    ) -> Self:
        """Append an object annotation."""
        return self.annotate_literal(prop, OBOLiteral.integer(value), annotations=annotations)

    def annotate_float(
        self, prop: ReferenceHint, value: float, *, annotations: Iterable[Annotation] | None = None
    ) -> Self:
        """Append a float annotation."""
        return self.annotate_literal(prop, OBOLiteral.float(value), annotations=annotations)

    def annotate_decimal(
        self, prop: ReferenceHint, value: float, *, annotations: Iterable[Annotation] | None = None
    ) -> Self:
        """Append a decimal annotation."""
        return self.annotate_literal(prop, OBOLiteral.decimal(value), annotations=annotations)

    def annotate_year(
        self,
        prop: ReferenceHint,
        value: int | str,
        *,
        annotations: Iterable[Annotation] | None = None,
    ) -> Self:
        """Append a year annotation."""
        return self.annotate_literal(prop, OBOLiteral.year(value), annotations=annotations)

    def annotate_uri(
        self, prop: ReferenceHint, value: str, *, annotations: Iterable[Annotation] | None = None
    ) -> Self:
        """Append a URI annotation."""
        return self.annotate_literal(prop, OBOLiteral.uri(value), annotations=annotations)

    def annotate_datetime(
        self,
        prop: ReferenceHint,
        value: datetime.datetime | str,
        *,
        annotations: Iterable[Annotation] | None = None,
    ) -> Self:
        """Append a datetime annotation."""
        return self.annotate_literal(prop, OBOLiteral.datetime(value), annotations=annotations)

    def _iterate_obo_properties(
        self,
        *,
        ontology_prefix: str,
        skip_predicate_objects: Iterable[Reference] | None = None,
        skip_predicate_literals: Iterable[Reference] | None = None,
        typedefs: Mapping[ReferenceTuple, TypeDef],
    ) -> Iterable[str]:
        for line in _iterate_obo_relations(
            # the type checker seems to be a bit confused, this is an okay typing since we're
            # passing a more explicit version. The issue is that list is used for the typing,
            # which means it can't narrow properly
            self.properties,  # type:ignore
            self._axioms,
            ontology_prefix=ontology_prefix,
            skip_predicate_objects=skip_predicate_objects,
            skip_predicate_literals=skip_predicate_literals,
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
        annotations: Iterable[Annotation] | None = None,
    ) -> Self:
        """Append an object annotation."""
        typedef = _ensure_ref(typedef)
        value = _ensure_ref(value)
        self.properties[typedef].append(value)
        self._extend_annotations(typedef, value, annotations)
        return self

    def append_contributor(self, reference: ReferenceHint) -> Self:
        """Append contributor."""
        return self.annotate_object(v.has_contributor, reference)

    def append_creation_date(self, date: datetime.datetime | str) -> Self:
        """Append contributor."""
        return self.annotate_datetime(v.obo_creation_date, date)

    def get_see_also(self) -> list[Reference]:
        """Get all see also objects."""
        return self.get_property_objects(v.see_also)

    def get_replaced_by(self) -> list[Reference]:
        """Get all replaced by."""
        return self.get_property_objects(v.term_replaced_by)

    def append_replaced_by(
        self, reference: Reference, *, annotations: Iterable[Annotation] | None = None
    ) -> Self:
        """Add a replaced by property."""
        return self.annotate_object(v.term_replaced_by, reference, annotations=annotations)

    def iterate_relations(self) -> Iterable[tuple[Reference, Reference]]:
        """Iterate over pairs of typedefs and targets."""
        for typedef, targets in sorted(self.relationships.items()):
            for target in sorted(targets):
                yield typedef, target

    def iterate_object_properties(self) -> Iterable[tuple[Reference, Reference]]:
        """Iterate over properties with references as their targets."""
        for predicate, values in self.properties.items():
            for value in values:
                if isinstance(value, Reference):
                    yield predicate, value

    def iterate_literal_properties(self) -> Iterable[tuple[Reference, OBOLiteral]]:
        """Iterate over properties with literals as their targets."""
        for predicate, values in self.properties.items():
            for value in values:
                if isinstance(value, OBOLiteral):
                    yield predicate, value

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
            for value in sorted(values, key=_reference_or_literal_key)
        ]

    def get_property_values(self, typedef: ReferenceHint) -> list[Reference | OBOLiteral]:
        """Iterate over references or values."""
        return sorted(self.properties.get(_ensure_ref(typedef), []))

    def get_property_objects(self, prop: ReferenceHint) -> list[Reference]:
        """Get properties from the given key."""
        return sorted(
            reference
            for reference in self.properties.get(_ensure_ref(prop), [])
            if isinstance(reference, curies.Reference)
        )

    def append_exact_synonym(
        self,
        synonym: str | Synonym,
        *,
        type: Reference | Referenced | None = None,
        provenance: Sequence[Reference | OBOLiteral] | None = None,
        annotations: Iterable[Annotation] | None = None,
        language: str | None = None,
    ) -> Self:
        """Add an exact synonym."""
        return self.append_synonym(
            synonym,
            type=type,
            specificity="EXACT",
            provenance=provenance,
            annotations=annotations,
            language=language,
        )

    def append_synonym(
        self,
        synonym: str | Synonym,
        *,
        type: Reference | Referenced | None = None,
        specificity: SynonymScope | None = None,
        provenance: Sequence[Reference | OBOLiteral] | None = None,
        annotations: Iterable[Annotation] | None = None,
        language: str | None = None,
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
                provenance=list(provenance or []),
                annotations=list(annotations or []),
                language=language,
            )
        self.synonyms.append(synonym)
        return self

    def append_alt(
        self, alt: Reference, *, annotations: Iterable[Annotation] | None = None
    ) -> Self:
        """Add an alternative identifier."""
        return self.annotate_object(v.alternative_term, alt, annotations=annotations)

    def append_see_also(
        self, reference: ReferenceHint, *, annotations: Iterable[Annotation] | None = None
    ) -> Self:
        """Add a see also property."""
        _reference = _ensure_ref(reference)
        return self.annotate_object(v.see_also, _reference, annotations=annotations)

    def append_comment(
        self,
        value: str,
        *,
        annotations: Iterable[Annotation] | None = None,
        language: str | None = None,
    ) -> Self:
        """Add a comment property."""
        return self.annotate_string(v.comment, value, annotations=annotations, language=language)

    def get_comments(self) -> list[str]:
        """Get all comment strings."""
        return [x.value for x in self.get_property_values(v.comment) if isinstance(x, OBOLiteral)]

    @property
    def alt_ids(self) -> Sequence[Reference]:
        """Get alternative terms."""
        return tuple(self.get_property_objects(v.alternative_term))

    def get_edges(self, *, include_xrefs: bool = True) -> list[tuple[Reference, Reference]]:
        """Get edges."""
        return list(self._iter_edges(include_xrefs=include_xrefs))

    def _iter_parents(self) -> Iterable[tuple[Reference, Reference]]:
        parent_prop = stanza_type_to_prop[self.type]
        for parent in itt.chain(self.parents, self.union_of):
            yield parent_prop, parent

    def _iter_intersections(self) -> Iterable[tuple[Reference, Reference]]:
        parent_prop = stanza_type_to_prop[self.type]
        for intersection_of in self.intersection_of:
            match intersection_of:
                case Reference():
                    yield parent_prop, intersection_of
                case (predicate, target):
                    yield predicate, target

    def _iter_edges(self, *, include_xrefs: bool = True) -> Iterable[tuple[Reference, Reference]]:
        # The following are "object" properties, meaning
        # they're part of the definition of the object
        yield from self.iterate_relations()
        yield from self._iter_parents()
        yield from self._iter_intersections()
        for equivalent_to in self.equivalent_to:
            yield stanza_type_to_eq_prop[self.type], equivalent_to

        # The following are "annotation" properties
        for subset in self.subsets:
            yield v.in_subset, subset
        yield from self.iterate_object_properties()

        if include_xrefs:
            for xref_reference in self.xrefs:
                yield v.has_dbxref, xref_reference

        # TODO disjoint_from

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

    def _get_object_annotation_target(
        self, p: Reference, o: Reference | OBOLiteral, ap: Reference
    ) -> Reference | None:
        match self._get_annotation(p, o, ap):
            case OBOLiteral():
                raise TypeError
            case Reference() as target:
                return target
            case None:
                return None
            case _:
                raise TypeError

    def _get_str_annotation_target(
        self, p: Reference, o: Reference | OBOLiteral, ap: Reference
    ) -> str | None:
        match self._get_annotation(p, o, ap):
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
            justification=self._get_object_annotation_target(p, o, v.mapping_has_justification)
            or unspecified_matching,
            contributor=self._get_object_annotation_target(p, o, v.has_contributor),
            confidence=self._get_str_annotation_target(p, o, v.mapping_has_confidence),
        )

    def _definition_fp(self) -> str:
        definition = obo_escape_slim(self.definition) if self.definition else ""
        dp = self._get_definition_provenance()
        if dp:
            return f'"{definition}" [{comma_separate_references(dp)}]'
        else:
            return f'"{definition}"'

    def _get_definition_provenance(self) -> Sequence[Reference | OBOLiteral]:
        if self.definition is None:
            return []
        return [
            annotation.value
            for annotation in self._get_annotations(v.has_description, self.definition)
            if annotation.predicate.pair == v.has_dbxref.pair
        ]

    @property
    def provenance(self) -> Sequence[Reference | OBOLiteral]:
        """Get definition provenance."""
        # return as a tuple to make sure nobody is appending on it
        return (
            *self.get_property_objects(v.has_citation),
            # This gets all of the xrefs on _any_ axiom,
            # which includes the definition provenance
            *(
                annotation.value
                for annotation in itt.chain.from_iterable(self._axioms.values())
                if annotation.predicate.pair == v.has_dbxref.pair
            ),
        )

    def append_definition_xref(self, reference: ReferenceHint) -> Self:
        """Add a reference to this term's definition."""
        if not self.definition:
            raise ValueError("can not append definition provenance if no definition is set")
        self._append_annotation(
            v.has_description,
            OBOLiteral.string(self.definition),
            Annotation(v.has_dbxref, _ensure_ref(reference)),
        )
        return self

    def append_provenance(
        self,
        reference: Reference,
        *,
        annotations: Iterable[Annotation] | None = None,
    ) -> Self:
        """Append a citation."""
        return self.annotate_object(v.has_citation, reference, annotations=annotations)


ReferenceHint: TypeAlias = (
    Reference | Referenced | curies.Reference | curies.NamedReference | tuple[str, str] | str
)


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
    if isinstance(reference, curies.NamedReference):
        return Reference(
            prefix=reference.prefix, identifier=reference.identifier, name=reference.name
        )
    if isinstance(reference, curies.Reference):
        return Reference(prefix=reference.prefix, identifier=reference.identifier)

    match _parse_str_or_curie_or_uri_helper(reference, ontology_prefix=ontology_prefix):
        case Reference() as parsed_reference:
            return parsed_reference
        case NotCURIEError() as exc:
            if ontology_prefix and _is_valid_identifier(reference):
                return default_reference(ontology_prefix, reference)
            else:
                raise exc
        case ParseError() as exc:
            raise exc

    raise TypeError


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
    annotations: AnnotationsDict,
    *,
    ontology_prefix: str,
    skip_predicate_objects: Iterable[Reference] | None = None,
    skip_predicate_literals: Iterable[Reference] | None = None,
    typedefs: Mapping[ReferenceTuple, TypeDef],
) -> Iterable[str]:
    """Iterate over relations/property values for OBO."""
    skip_predicate_objects = set(skip_predicate_objects or [])
    skip_predicate_literals = set(skip_predicate_literals or [])
    for predicate, values in sorted(relations.items()):
        _typedef_warn(prefix=ontology_prefix, predicate=predicate, typedefs=typedefs)
        pc = reference_escape(predicate, ontology_prefix=ontology_prefix)
        start = f"{pc} "
        for value in sorted(values, key=_reference_or_literal_key):
            match value:
                case OBOLiteral(dd, datatype, _language):
                    if predicate in skip_predicate_literals:
                        continue
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


def _reference_or_literal_key(x: Reference | OBOLiteral) -> tuple[int, Reference | OBOLiteral]:
    if isinstance(x, Reference):
        return 0, x
    else:
        return 1, x


def _get_obo_trailing_modifiers(
    p: ReferenceHint,
    o: Reference | OBOLiteral,
    annotations_dict: AnnotationsDict,
    *,
    ontology_prefix: str,
) -> str:
    """Lookup then format a sequence of annotations for OBO trailing modifiers."""
    if annotations := annotations_dict.get(_property_resolve(p, o), []):
        return _format_obo_trailing_modifiers(annotations, ontology_prefix=ontology_prefix)
    return ""


def _format_obo_trailing_modifiers(
    annotations: Sequence[Annotation], *, ontology_prefix: str
) -> str:
    """Format a sequence of annotations for OBO trailing modifiers.

    :param annotations: A list of annnotations
    :param ontology_prefix: The ontology prefix

    :returns: The trailing modifiers string

    See https://owlcollab.github.io/oboformat/doc/GO.format.obo-1_4.html#S.1.4 trailing
    modifiers can be both annotations and some other implementation-specific things, so
    split up the place where annotations are put in here.
    """
    modifiers: list[tuple[str, str]] = []
    for prop in sorted(annotations, key=Annotation._sort_key):
        left = reference_escape(prop.predicate, ontology_prefix=ontology_prefix)
        match prop.value:
            case Reference():
                right = reference_escape(prop.value, ontology_prefix=ontology_prefix)
            case OBOLiteral(value, _datatype, _language):
                right = value
        modifiers.append((left, right))
    inner = ", ".join(f"{key}={value}" for key, value in modifiers)
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


def _get_prefixes_from_annotations(annotations: Iterable[Annotation]) -> set[str]:
    return set(_get_references_from_annotations(annotations))


def _get_references_from_annotations(
    annotations: Iterable[Annotation],
) -> dict[str, set[Reference]]:
    rv: defaultdict[str, set[Reference]] = defaultdict(set)
    for left, right in annotations:
        rv[left.prefix].add(left)
        if isinstance(right, Reference):
            rv[right.prefix].add(right)
    return dict(rv)


def _get_stanza_name_synonym(stanza: Stanza) -> LiteralMapping:
    return LiteralMapping(
        text=stanza.reference.name,
        reference=stanza.reference,
        predicate=_v.has_label,
        type=None,
        provenance=[p for p in stanza.provenance if isinstance(p, curies.Reference)],
        contributor=None,  # TODO
        comment=None,  # TODO
        source=stanza.reference.prefix,
        date=None,  # TODO
    )


def _convert_synoynym(stanza: Stanza, synonym: Synonym) -> LiteralMapping:
    o = OBOLiteral.string(synonym.name, language=synonym.language)
    # TODO make this indexing reusable? similar code used for SSSOM export
    idx: dict[Reference, Reference | OBOLiteral] = {
        annotation.predicate: annotation.value
        for annotation in stanza._get_annotations(synonym.predicate, o)
    }

    comment = _safe_str(idx.get(v.comment))
    contributor = _safe_str(idx.get(v.has_contributor))
    date = _safe_str(idx.get(v.has_date))

    return LiteralMapping(
        text=synonym.name,
        language=synonym.language,
        reference=stanza.reference,
        predicate=synonym.predicate,
        type=synonym.type,
        provenance=[p for p in synonym.provenance if isinstance(p, curies.Reference)],
        contributor=contributor,
        comment=comment,
        source=stanza.reference.prefix,
        date=date,
    )


def _safe_str(x: Reference | OBOLiteral | None) -> str | None:
    if x is None:
        return None
    return reference_or_literal_to_str(x)
