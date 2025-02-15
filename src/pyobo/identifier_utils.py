"""Utilities for handling prefixes."""

from __future__ import annotations

import logging
from functools import wraps
from typing import Annotated, ClassVar

import bioontologies.upgrade
import bioregistry
from curies import ReferenceTuple
from pydantic import ValidationError
from typing_extensions import Doc

from ._reference_tmp import Reference
from .registries import (
    curie_has_blacklisted_prefix,
    curie_has_blacklisted_suffix,
    curie_is_blacklisted,
    remap_full,
    remap_prefix,
)

__all__ = [
    "_parse_str_or_curie_or_uri_helper",
    "standardize_ec",
    "wrap_norm_prefix",
]

logger = logging.getLogger(__name__)


class BlacklistedError(ValueError):
    """A sentinel for blacklisted strings."""


Line = Annotated[str | None, Doc("""The OBO line where the parsing happened""")]


class ParseError(BaseException):
    """Raised on a missing prefix."""

    text: ClassVar[str]

    def __init__(
        self,
        curie: str,
        *,
        context: str | None,
        ontology_prefix: str | None = None,
        node: Reference | None = None,
        line: Line = None,
    ) -> None:
        """Initialize the error."""
        self.curie = curie
        self.context = context
        self.ontology_prefix = ontology_prefix
        self.node = node
        self.line = line

    def __str__(self) -> str:
        s = ""
        if self.node:
            s += f"[{self.node.curie}] "
        elif self.ontology_prefix:
            s += f"[{self.ontology_prefix}] "
        s += f"`{self.curie}` {self.text}"
        if self.line:
            s += f" in: {self.line}"
        return s


class ParseValidationError(ParseError):
    """Raised on a validation error."""

    text = "failed Pydantic validation"

    def __init__(self, *args, exc: ValidationError, **kwargs) -> None:
        """Initialize the error."""
        super().__init__(*args, **kwargs)
        self.exc = exc


class UnregisteredPrefixError(ParseError):
    """Raised on a missing prefix."""

    text = "contains unhandled prefix"


class UnparsableIRIError(ParseError):
    """Raised on a an unparsable IRI."""

    text = "could not be IRI parsed"


class EmptyStringError(ParseError):
    """Raised on a an empty string."""

    text = "is empty"


class NotCURIEError(ParseError):
    """Raised on a text that can't be parsed as a CURIE."""

    text = "Not a CURIE"


class DefaultCoercionError(ParseError):
    """Raised on a text that can't be coerced into a default reference."""

    text = "can't be coerced into a default reference"


def _is_uri(s: str) -> bool:
    return s.startswith("http:") or s.startswith("https:")


def _preclean_uri(s: str) -> str:
    s = s.strip().removeprefix("url:").removeprefix("uri:")
    s = s.removeprefix("URL:").removeprefix("URI:")
    s = s.removeprefix("WWW:").removeprefix("www:").lstrip()
    s = s.replace("http\\:", "http:")
    s = s.replace("https\\:", "https:")
    return s


def _parse_str_or_curie_or_uri_helper(
    str_or_curie_or_uri: str,
    *,
    ontology_prefix: str | None = None,
    node: Reference | None = None,
    upgrade: bool = True,
    line: str | None = None,
    name: str | None = None,
    context: str | None = None,
) -> Reference | ParseError | BlacklistedError:
    """Parse a string that looks like a CURIE.

    :param str_or_curie_or_uri: A compact uniform resource identifier (CURIE)
    :param ontology_prefix: The ontology in which the CURIE appears

    :returns: A parse tuple or a tuple of None, None if not able to parse and not strict

    - Normalizes the namespace
    - Checks against a blacklist for the entire curie, for the namespace, and for
      suffixes.
    """
    str_or_curie_or_uri = _preclean_uri(str_or_curie_or_uri)
    if not str_or_curie_or_uri:
        raise EmptyStringError(
            str_or_curie_or_uri,
            ontology_prefix=ontology_prefix,
            node=node,
            line=line,
            context=context,
        )

    if upgrade:
        # Remap the curie with the full list
        str_or_curie_or_uri = remap_full(str_or_curie_or_uri)

        # Remap node's prefix (if necessary)
        str_or_curie_or_uri = remap_prefix(str_or_curie_or_uri, ontology_prefix=ontology_prefix)

    if curie_is_blacklisted(str_or_curie_or_uri):
        return BlacklistedError()
    if curie_has_blacklisted_prefix(str_or_curie_or_uri):
        return BlacklistedError()
    if curie_has_blacklisted_suffix(str_or_curie_or_uri):
        return BlacklistedError()

    if upgrade and (reference_t := bioontologies.upgrade.upgrade(str_or_curie_or_uri)):
        return Reference(prefix=reference_t.prefix, identifier=reference_t.identifier)

    if _is_uri(str_or_curie_or_uri):
        prefix, identifier = bioregistry.parse_iri(str_or_curie_or_uri)
        if prefix and identifier:
            return Reference(prefix=prefix, identifier=identifier)
        else:
            return UnparsableIRIError(
                str_or_curie_or_uri,
                ontology_prefix=ontology_prefix,
                node=node,
                line=line,
                context=context,
            )

    prefix, delimiter, identifier = str_or_curie_or_uri.partition(":")
    if not delimiter:
        return NotCURIEError(
            str_or_curie_or_uri,
            ontology_prefix=ontology_prefix,
            node=node,
            line=line,
            context=context,
        )

    norm_node_prefix = bioregistry.normalize_prefix(prefix)
    if not norm_node_prefix:
        return UnregisteredPrefixError(
            str_or_curie_or_uri,
            ontology_prefix=ontology_prefix,
            node=node,
            line=line,
            context=context,
        )

    identifier = bioregistry.standardize_identifier(norm_node_prefix, identifier)
    try:
        rv = Reference.model_validate(
            {"prefix": norm_node_prefix, "identifier": identifier, "name": name}
        )
    except ValidationError as exc:
        return ParseValidationError(
            str_or_curie_or_uri,
            ontology_prefix=ontology_prefix,
            node=node,
            line=line,
            exc=exc,
            context=context,
        )
    else:
        return rv


def wrap_norm_prefix(f):
    """Decorate a function that take in a prefix to auto-normalize, or return None if it can't be normalized."""

    @wraps(f)
    def _wrapped(prefix: str | Reference | ReferenceTuple, *args, **kwargs):
        if isinstance(prefix, str):
            norm_prefix = bioregistry.normalize_prefix(prefix)
            if norm_prefix is None:
                raise ValueError(f"Invalid prefix: {prefix}")
            prefix = norm_prefix
        elif isinstance(prefix, Reference):
            norm_prefix = bioregistry.normalize_prefix(prefix.prefix)
            if norm_prefix is None:
                raise ValueError(f"Invalid prefix: {prefix.prefix}")
            prefix = Reference(prefix=norm_prefix, identifier=prefix.identifier)
        elif isinstance(prefix, ReferenceTuple):
            norm_prefix = bioregistry.normalize_prefix(prefix.prefix)
            if norm_prefix is None:
                raise ValueError(f"Invalid prefix: {prefix.prefix}")
            prefix = ReferenceTuple(norm_prefix, prefix.identifier)
        else:
            raise TypeError
        return f(prefix, *args, **kwargs)

    return _wrapped


def standardize_ec(ec: str) -> str:
    """Standardize an EC code identifier by removing all trailing dashes and dots."""
    ec = ec.strip().replace(" ", "")
    for _ in range(4):
        ec = ec.rstrip("-").rstrip(".")
    return ec


def _is_valid_identifier(curie_or_uri: str) -> bool:
    # TODO this needs more careful implementation
    return bool(curie_or_uri.strip()) and " " not in curie_or_uri
