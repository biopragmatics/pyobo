"""Data structures for OBO."""

from __future__ import annotations

import datetime
import logging
from collections import Counter
from collections.abc import Iterable, Sequence
from typing import Any, NamedTuple

import bioregistry
import curies
import dateutil.parser
import pytz
from bioregistry import NormalizedNamableReference as Reference
from curies import ReferenceTuple
from curies.preprocessing import BlocklistError

from ..identifier_utils import (
    NotCURIEError,
    ParseError,
    UnparsableIRIError,
    _is_valid_identifier,
    _parse_str_or_curie_or_uri_helper,
)

__all__ = [
    "Referenced",
    "default_reference",
    "get_preferred_curie",
    "multi_reference_escape",
    "reference_escape",
    "unspecified_matching",
]

logger = logging.getLogger(__name__)


def _parse_str_or_curie_or_uri(
    str_curie_or_uri: str,
    name: str | None = None,
    *,
    strict: bool = False,
    ontology_prefix: str | None = None,
    node: Reference | None = None,
    predicate: Reference | None = None,
    line: str | None = None,
    context: str | None = None,
    upgrade: bool = False,
) -> Reference | None:
    reference = _parse_str_or_curie_or_uri_helper(
        str_curie_or_uri,
        ontology_prefix=ontology_prefix,
        name=name,
        node=node,
        predicate=predicate,
        line=line,
        context=context,
        upgrade=upgrade,
    )

    match reference:
        case Reference():
            return reference
        case BlocklistError():
            return None
        case ParseError():
            if strict:
                raise reference
            else:
                return None
        case _:
            raise TypeError(f"Got invalid: ({type(reference)}) {reference}")


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
    def pair(self) -> ReferenceTuple:
        """The pair of namespace/identifier."""
        return self.reference.pair


def get_preferred_prefix(
    ref: curies.Reference | Reference | Referenced,
) -> str:
    """Get the preferred prefix from a variety of types."""
    match ref:
        case Referenced() | Reference():
            return bioregistry.get_preferred_prefix(ref.prefix) or ref.prefix
        case curies.Reference():
            return ref.prefix


def get_preferred_curie(
    ref: curies.Reference | Reference | Referenced,
) -> str:
    """Get the preferred CURIE from a variety of types."""
    match ref:
        case Referenced() | Reference():
            return f"{get_preferred_prefix(ref)}:{ref.identifier}"
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


def _obo_parse_identifier(
    str_or_curie_or_uri: str,
    *,
    ontology_prefix: str,
    strict: bool = False,
    node: Reference | None = None,
    predicate: Reference | None = None,
    line: str | None = None,
    context: str | None = None,
    name: str | None = None,
    upgrade: bool = True,
    counter: Counter[tuple[str, str]] | None = None,
) -> Reference | None:
    """Parse from a CURIE, URI, or default string in the ontology prefix's IDspace using OBO semantics."""
    match _parse_str_or_curie_or_uri_helper(
        str_or_curie_or_uri,
        ontology_prefix=ontology_prefix,
        node=node,
        predicate=predicate,
        line=line,
        context=context,
        name=name,
        upgrade=upgrade,
    ):
        case Reference() as reference:
            return reference
        case BlocklistError():
            return None
        case NotCURIEError() as exc:
            # this means there's no colon `:`
            if _is_valid_identifier(str_or_curie_or_uri):
                return default_reference(prefix=ontology_prefix, identifier=str_or_curie_or_uri)
            elif strict:
                raise exc
            else:
                return None
        case ParseError() as exc:
            if strict:
                raise exc
            if counter is None:
                logger.warning(str(exc))
            else:
                if not counter[ontology_prefix, str_or_curie_or_uri]:
                    logger.warning(str(exc))
                counter[ontology_prefix, str_or_curie_or_uri] += 1
            return None


def _parse_reference_or_uri_literal(
    str_or_curie_or_uri: str,
    *,
    ontology_prefix: str,
    strict: bool = False,
    node: Reference,
    predicate: Reference | None = None,
    line: str,
    context: str,
    name: str | None = None,
    upgrade: bool = True,
    #
    counter: Counter[tuple[str, str]] | None = None,
) -> None | Reference | OBOLiteral:
    match _parse_str_or_curie_or_uri_helper(
        str_or_curie_or_uri,
        node=node,
        predicate=predicate,
        ontology_prefix=ontology_prefix,
        line=line,
        context=context,
        name=name,
        upgrade=upgrade,
    ):
        case Reference() as reference:
            return reference
        case BlocklistError():
            return None
        case UnparsableIRIError():
            # this means that it's defininitely a URI,
            # but it couldn't be parsed with Bioregistry
            return OBOLiteral.uri(str_or_curie_or_uri)
        case NotCURIEError() as exc:
            # this means there's no colon `:`
            if _is_valid_identifier(str_or_curie_or_uri):
                return default_reference(prefix=ontology_prefix, identifier=str_or_curie_or_uri)
            elif strict:
                raise exc
            else:
                return None
        case ParseError() as exc:
            if strict:
                raise exc
            if counter is None:
                logger.warning(str(exc))
            else:
                if not counter[ontology_prefix, str_or_curie_or_uri]:
                    logger.warning(str(exc))
                counter[ontology_prefix, str_or_curie_or_uri] += 1
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
