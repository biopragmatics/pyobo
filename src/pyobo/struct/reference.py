"""Data structures for OBO."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from typing import Any, NamedTuple

import bioontologies.relations
import bioontologies.upgrade
import bioregistry
import curies
from curies import Converter, ReferenceTuple
from curies.api import ExpansionError, _split
from pydantic import Field, field_validator, model_validator

from .utils import obo_escape
from ..constants import GLOBAL_CHECK_IDS
from ..identifier_utils import normalize_curie

__all__ = [
    "Reference",
    "Referenced",
    "default_reference",
    "get_preferred_curie",
    "multi_reference_escape",
    "reference_escape",
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

    # override from_curie to get typing right
    @classmethod
    def from_curie(
        cls, curie: str, *, sep: str = ":", converter: Converter | None = None
    ) -> Reference:
        """Parse a CURIE string and populate a reference.

        :param curie: A string representation of a compact URI (CURIE)
        :param sep: The separator
        :param converter: The converter to use as context when parsing
        :return: A reference object

        >>> Reference.from_curie("chebi:1234")
        Reference(prefix='CHEBI', identifier='1234')
        """
        prefix, identifier = _split(curie, sep=sep)
        return cls.model_validate({"prefix": prefix, "identifier": identifier}, context=converter)

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


def get_preferred_curie(
    ref: curies.Reference | curies.NamedReference | Reference | Referenced,
) -> str:
    """Get the preferred CURIE from a variety of types."""
    match ref:
        case Referenced() | Reference():
            return ref.preferred_curie
        case curies.Reference() | curies.NamedReference():
            return ref.curie


def default_reference(prefix: str, identifier: str, name: str | None = None) -> Reference:
    """Create a CURIE for an "unqualified" reference.

    :param prefix: The prefix of the ontology in which the "unqualified" reference is made
    :param identifier: The "unqualified" reference. For example, if you just write
        "located_in" somewhere there is supposed to be a CURIE
    :returns: A CURIE for the "unqualified" reference based on the OBO semantic space

    >>> default_reference("chebi", "conjugate_base_of")
    Reference(prefix="obo", identifier="chebi#conjugate_base_of", name=None)
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
    rv = get_preferred_curie(reference)
    if add_name_comment and reference.name:
        rv += f" ! {reference.name}"
    return rv


def multi_reference_escape(
    references: Sequence[Reference | Reference],
    *,
    ontology_prefix: str,
    add_name_comment: bool = False,
) -> str:
    """Write multiple references with default namespace normalized."""
    rv = " ".join(
        reference_escape(r, ontology_prefix=ontology_prefix, add_name_comment=False)
        for r in references
    )
    names = [r.name or "" for r in references]
    if add_name_comment and all(names):
        rv += " ! " + " ".join(names)
    return rv


def comma_separate_references(elements: Iterable[Reference | OBOLiteral]) -> str:
    """Map a list to strings and make comma separated."""
    parts = []
    for element in elements:
        match element:
            case Reference():
                parts.append(get_preferred_curie(element))
            case OBOLiteral(value, _datatype):
                # TODO check datatype is URI
                parts.append(value)
    return ", ".join(parts)


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

    @classmethod
    def string(cls, value: str) -> OBOLiteral:
        """Get a string literal."""
        return cls(value, Reference(prefix="xsd", identifier="string"))

    @classmethod
    def uri(cls, uri: str) -> OBOLiteral:
        """Get a string literal for a URI."""
        return cls(uri, Reference(prefix="xsd", identifier="anyURI"))


def _reference_list_tag(
    tag: str, references: Iterable[Reference], ontology_prefix: str
) -> Iterable[str]:
    for reference in references:
        yield f"{tag}: {reference_escape(reference, ontology_prefix=ontology_prefix, add_name_comment=True)}"
