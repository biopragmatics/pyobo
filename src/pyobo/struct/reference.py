"""Data structures for OBO."""

from __future__ import annotations

import datetime
import logging
from collections.abc import Iterable, Sequence
from typing import Any, NamedTuple

import bioontologies.relations
import bioontologies.upgrade
import bioregistry
import curies
import dateutil.parser
import pytz
from curies import ReferenceTuple
from curies.api import ExpansionError
from pydantic import ValidationError, model_validator

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

logger = logging.getLogger(__name__)


class Reference(curies.NamableReference):
    """A namespace, identifier, and label."""

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
        if " " in identifier:
            raise ValueError(f"[{prefix}] space in identifier: {identifier}")
        values["identifier"] = resource.standardize_identifier(identifier)
        if GLOBAL_CHECK_IDS and not resource.is_valid_identifier(values["identifier"]):
            raise ValueError(f"non-standard identifier: {resource.prefix}:{values['identifier']}")
        return values

    def as_named_reference(self, name: str | None = None) -> curies.NamedReference:
        """Get a named reference."""
        if not self.name:
            if name:
                logger.warning("[%s] missing name; overriding with synonym: %s", self.curie, name)
            else:
                raise ValueError(f"[{self.curie}] missing name; can't convert to named reference")
        return curies.NamedReference(
            prefix=self.prefix, identifier=self.identifier, name=self.name or name
        )

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
        try:
            rv = cls.model_validate({"prefix": prefix, "identifier": identifier, "name": name})
        except ValidationError:
            if strict:
                raise
            return None
        else:
            return rv

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
    ref: curies.Reference | Reference | Referenced,
) -> str:
    """Get the preferred CURIE from a variety of types."""
    match ref:
        case Referenced() | Reference():
            return ref.preferred_curie
        case curies.Reference():
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


def _get_ref_name(reference: curies.Reference | Referenced) -> str | None:
    if isinstance(reference, curies.NamableReference | Referenced):
        return reference.name
    return None


def reference_escape(
    reference: curies.Reference | Referenced,
    *,
    ontology_prefix: str,
    add_name_comment: bool = False,
) -> str:
    """Write a reference with default namespace removed."""
    if reference.prefix == "obo" and reference.identifier.startswith(f"{ontology_prefix}#"):
        return reference.identifier.removeprefix(f"{ontology_prefix}#")
    rv = get_preferred_curie(reference)
    if add_name_comment and (name := _get_ref_name(reference)):
        rv += f" ! {name}"
    return rv


def multi_reference_escape(
    references: Sequence[Reference | Referenced],
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
    return ", ".join(reference_or_literal_to_str(element) for element in elements)


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
    try:
        if upgrade:
            if xx := bioontologies.upgrade.upgrade(s):
                return Reference(prefix=xx.prefix, identifier=xx.identifier, name=name)
            if yy := _ground_relation(s):
                return Reference(prefix=yy.prefix, identifier=yy.identifier, name=name)
        return default_reference(ontology_prefix, s, name=name)
    except ValidationError:
        return None


unspecified_matching = Reference(
    prefix="semapv", identifier="UnspecifiedMatching", name="unspecified matching process"
)


class OBOLiteral(NamedTuple):
    """A tuple representing a property with a literal value."""

    value: str
    datatype: curies.Reference
    language: str | None

    @classmethod
    def string(cls, value: str, *, language: str | None = None) -> OBOLiteral:
        """Get a string literal."""
        return cls(value, curies.Reference(prefix="xsd", identifier="string"), language)

    @classmethod
    def boolean(cls, value: bool) -> OBOLiteral:
        """Get a boolean literal."""
        return cls(str(value).lower(), curies.Reference(prefix="xsd", identifier="boolean"), None)

    @classmethod
    def decimal(cls, value) -> OBOLiteral:
        """Get a decimal literal."""
        return cls(str(value), curies.Reference(prefix="xsd", identifier="decimal"), None)

    @classmethod
    def float(cls, value) -> OBOLiteral:
        """Get a float literal."""
        return cls(str(value), curies.Reference(prefix="xsd", identifier="float"), None)

    @classmethod
    def integer(cls, value: int | str) -> OBOLiteral:
        """Get a integer literal."""
        return cls(str(int(value)), curies.Reference(prefix="xsd", identifier="integer"), None)

    @classmethod
    def year(cls, value: int | str) -> OBOLiteral:
        """Get a year (gYear) literal."""
        return cls(str(int(value)), curies.Reference(prefix="xsd", identifier="gYear"), None)

    @classmethod
    def uri(cls, uri: str) -> OBOLiteral:
        """Get a string literal for a URI."""
        return cls(uri, curies.Reference(prefix="xsd", identifier="anyURI"), None)

    @classmethod
    def datetime(cls, dt: datetime.datetime | str) -> OBOLiteral:
        """Get a datetime literal."""
        if isinstance(dt, str):
            dt = _parse_datetime(dt)
        return cls(dt.isoformat(), curies.Reference(prefix="xsd", identifier="dateTime"), None)


def _parse_datetime(dd: str) -> datetime.datetime:
    xx = dateutil.parser.parse(dd)
    xx = xx.astimezone(pytz.UTC)
    return xx


def _reference_list_tag(
    tag: str, references: Iterable[Reference], ontology_prefix: str
) -> Iterable[str]:
    for reference in references:
        yield f"{tag}: {reference_escape(reference, ontology_prefix=ontology_prefix, add_name_comment=True)}"


def reference_or_literal_to_str(x: OBOLiteral | curies.Reference | Reference | Referenced) -> str:
    """Get a string from a reference or literal."""
    if isinstance(x, OBOLiteral):
        return x.value
    return get_preferred_curie(x)
