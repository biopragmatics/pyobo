"""Data structures for OBO."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from typing import Any, NamedTuple

import bioontologies.relations
import bioontologies.upgrade
import bioregistry
import curies
from curies import ReferenceTuple
from curies.api import ExpansionError
from pydantic import Field, field_validator, model_validator

from .utils import obo_escape
from ..constants import GLOBAL_CHECK_IDS
from ..identifier_utils import normalize_curie

__all__ = [
    "Reference",
    "Referenced",
    "default_reference",
    "unspecified_matching",
]


class Reference(curies.Reference):
    """A namespace, identifier, and label."""

    name: str | None = Field(default=None, description="the name of the reference")

    @field_validator("prefix")
    def validate_prefix(cls, v):  # noqa
        """Validate the prefix for this reference."""
        norm_prefix = bioregistry.normalize_prefix(v)
        if norm_prefix is None:
            raise ExpansionError(f"Unknown prefix: {v}")
        return norm_prefix

    @property
    def preferred_prefix(self) -> str:
        """Get the preferred curie for this reference."""
        return bioregistry.get_preferred_prefix(self.prefix) or self.prefix

    @property
    def preferred_curie(self) -> str:
        """Get the preferred curie for this reference."""
        return f"{self.preferred_prefix}:{self.identifier}"

    @model_validator(mode="before")
    def validate_identifier(cls, values):  # noqa
        """Validate the identifier."""
        prefix, identifier = values.get("prefix"), values.get("identifier")
        if not prefix or not identifier:
            return values
        resource = bioregistry.get_resource(prefix)
        if resource is None:
            raise ExpansionError(f"Unknown prefix: {prefix}")
        values["prefix"] = resource.prefix
        values["identifier"] = resource.standardize_identifier(identifier)
        if GLOBAL_CHECK_IDS and not resource.is_valid_identifier(values["identifier"]):
            raise ValueError(f"non-standard identifier: {resource.prefix}:{values['identifier']}")
        return values

    @classmethod
    def auto(cls, prefix: str, identifier: str) -> Reference:
        """Create a reference and autopopulate its name."""
        from ..api import get_name

        name = get_name(prefix, identifier)
        return cls.model_validate({"prefix": prefix, "identifier": identifier, "name": name})

    @property
    def bioregistry_link(self) -> str:
        """Get the bioregistry link."""
        return f"https://bioregistry.io/{self.curie}"

    @classmethod
    def from_curie_or_uri(
        cls,
        curie: str,
        name: str | None = None,
        *,
        strict: bool = True,
        auto: bool = False,
        ontology_prefix: str | None = None,
        node: Reference | None = None,
    ) -> Reference | None:
        """Get a reference from a CURIE.

        :param curie: The compact URI (CURIE) to parse in the form of `<prefix>:<identifier>`
        :param name: The name associated with the CURIE
        :param strict: If true, raises an error if the CURIE can not be parsed.
        :param auto: Automatically look up name
        """
        prefix, identifier = normalize_curie(
            curie, strict=strict, ontology_prefix=ontology_prefix, node=node
        )
        if prefix is None or identifier is None:
            return None

        if name is None and auto:
            from ..api import get_name

            name = get_name(prefix, identifier)
        return cls.model_validate({"prefix": prefix, "identifier": identifier, "name": name})

    @property
    def _escaped_identifier(self):
        return obo_escape(self.identifier)

    def __str__(self) -> str:
        rv = f"{self.preferred_prefix}:{self._escaped_identifier}"
        if self.name:
            rv = f"{rv} ! {self.name}"
        return rv


class Referenced:
    """A class that contains a reference."""

    reference: Reference

    def __hash__(self) -> int:
        return self.reference.__hash__()

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, curies.Reference | Referenced):
            return self.prefix == other.prefix and self.identifier == other.identifier
        raise TypeError

    def __lt__(self, other: Referenced) -> bool:
        if not isinstance(other, curies.Reference | Referenced):
            raise TypeError
        return self.reference < other.reference

    @property
    def prefix(self):
        """The prefix of the typedef."""
        return self.reference.prefix

    @property
    def name(self):
        """The name of the typedef."""
        return self.reference.name

    @property
    def identifier(self) -> str:
        """The local unique identifier for this typedef."""
        return self.reference.identifier

    @property
    def curie(self) -> str:
        """The CURIE for this typedef."""
        return self.reference.curie

    @property
    def preferred_curie(self) -> str:
        """The preferred CURIE for this typedef."""
        return self.reference.preferred_curie

    @property
    def pair(self) -> ReferenceTuple:
        """The pair of namespace/identifier."""
        return self.reference.pair

    @property
    def bioregistry_link(self) -> str:
        """Get the bioregistry link."""
        return self.reference.bioregistry_link


def default_reference(prefix: str, identifier: str, name: str | None = None) -> Reference:
    """Create a CURIE for an "unqualified" reference.

    :param prefix: The prefix of the ontology in which the "unqualified" reference is made
    :param identifier: The "unqualified" reference. For example, if you just write
        "located_in" somewhere there is supposed to be a CURIE
    :returns: A CURIE for the "unqualified" reference based on the OBO semantic space

    >>> default_reference("chebi", "conjugate_base_of")
    Reference(prefix="obo", identifier="chebi#conjugate_base_of")
    """
    if not identifier.strip():
        raise ValueError("default identifier is empty")
    return Reference(prefix="obo", identifier=f"{prefix}#{identifier}", name=name)


def reference_escape(
    reference: Reference | Referenced, *, ontology_prefix: str, add_name_comment: bool = False
) -> str:
    """Write a reference with default namespace removed."""
    if reference.prefix == "obo" and reference.identifier.startswith(f"{ontology_prefix}#"):
        return reference.identifier.removeprefix(f"{ontology_prefix}#")
    # get sneaky, to allow a variety of the base class from curies.Reference to
    # the extended version in pyobo.Reference
    rv = getattr(reference, "preferred_curie", reference.curie)
    if add_name_comment and reference.name:
        rv += f" ! {reference.name}"
    return rv


def comma_separate_references(references: list[Reference]) -> str:
    """Map a list to strings and make comma separated."""
    return ", ".join(r.preferred_curie for r in references)


def _ground_relation(relation_str: str) -> Reference | None:
    prefix, identifier = bioontologies.relations.ground_relation(relation_str)
    if prefix and identifier:
        return Reference(prefix=prefix, identifier=identifier)
    return None


def _parse_identifier(
    s: str,
    *,
    ontology_prefix: str,
    strict: bool = True,
    node: Reference | None = None,
    name: str | None = None,
    upgrade: bool = True,
) -> Reference | None:
    """Parse from a CURIE, URI, or default string in the ontology prefix's IDspace."""
    if ":" in s:
        return Reference.from_curie_or_uri(
            s, ontology_prefix=ontology_prefix, name=name, strict=strict, node=node
        )
    if upgrade:
        if xx := bioontologies.upgrade.upgrade(s):
            return Reference(prefix=xx.prefix, identifier=xx.identifier, name=name)
        if yy := _ground_relation(s):
            return Reference(prefix=yy.prefix, identifier=yy.identifier, name=name)
    return default_reference(ontology_prefix, s, name=name)


unspecified_matching = Reference(
    prefix="semapv", identifier="UnspecifiedMatching", name="unspecified matching process"
)


class OBOLiteral(NamedTuple):
    """A tuple representing a property with a literal value."""

    value: str
    datatype: Reference


AxiomsHint = Mapping[
    tuple[Reference, Reference | OBOLiteral], Sequence[tuple[Reference, Reference | OBOLiteral]]
]


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


def _chain_tag(tag: str, chain: list[Reference] | None, ontology_prefix: str) -> Iterable[str]:
    if chain:
        yv = f"{tag}: "
        yv += " ".join(
            reference_escape(reference, ontology_prefix=ontology_prefix) for reference in chain
        )
        if any(reference.name for reference in chain):
            _names = " / ".join(link.name or "_" for link in chain)
            yv += f" ! {_names}"
        yield yv


def _reference_list_tag(
    tag: str, references: list[Reference], ontology_prefix: str
) -> Iterable[str]:
    for reference in references:
        yield f"{tag}: {reference_escape(reference, ontology_prefix=ontology_prefix, add_name_comment=True)}"
