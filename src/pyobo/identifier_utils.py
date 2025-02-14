"""Utilities for handling prefixes."""

from __future__ import annotations

import logging
from functools import wraps
from typing import ClassVar

import bioontologies.upgrade
import bioregistry
from curies import Reference, ReferenceTuple

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


class ParseError(ValueError):
    """Raised on a missing prefix."""

    text: ClassVar[str]

    def __init__(
        self,
        *,
        curie: str,
        ontology_prefix: str | None = None,
        node: Reference | None = None,
    ) -> None:
        """Initialize the error."""
        self.curie = curie
        self.ontology_prefix = ontology_prefix
        self.node = node

    def __str__(self) -> str:
        s = ""
        if self.ontology_prefix:
            s += f"[{self.ontology_prefix}] "
        s += f"{self.text}: `{self.curie}`"
        if self.node is not None:
            s += f" from {self.node.curie}"
        return s


class MissingPrefixError(ParseError):
    """Raised on a missing prefix."""

    text = "CURIE contains unhandled prefix"


class UnparsableIRIError(ParseError):
    """Raised on a an unparsable IRI."""

    text = "IRI could not be parsed"


BAD_CURIES = set()


def _parse_str_or_curie_or_uri_helper(
    str_or_curie_or_uri: str,
    *,
    strict: bool = True,
    ontology_prefix: str | None = None,
    node: Reference | None = None,
    upgrade: bool = True,
) -> ReferenceTuple | tuple[None, None]:
    """Parse a string that looks like a CURIE.

    :param str_or_curie_or_uri: A compact uniform resource identifier (CURIE)
    :param strict: Should an exception be thrown if the CURIE can not be parsed w.r.t.
        the Bioregistry?
    :param ontology_prefix: The ontology in which the CURIE appears

    :returns: A parse tuple or a tuple of None, None if not able to parse and not strict

    - Normalizes the namespace
    - Checks against a blacklist for the entire curie, for the namespace, and for
      suffixes.
    """
    if upgrade:
        # Remap the curie with the full list
        str_or_curie_or_uri = remap_full(str_or_curie_or_uri)

        # Remap node's prefix (if necessary)
        str_or_curie_or_uri = remap_prefix(str_or_curie_or_uri, ontology_prefix=ontology_prefix)

    if curie_is_blacklisted(str_or_curie_or_uri):
        return None, None
    if curie_has_blacklisted_prefix(str_or_curie_or_uri):
        return None, None
    if curie_has_blacklisted_suffix(str_or_curie_or_uri):
        return None, None

    if upgrade and (reference_t := bioontologies.upgrade.upgrade(str_or_curie_or_uri)):
        return reference_t

    if str_or_curie_or_uri.startswith("http:") or str_or_curie_or_uri.startswith("https:"):
        if reference_tuple := _parse_iri(str_or_curie_or_uri):
            return reference_tuple
        elif strict:
            raise UnparsableIRIError(
                curie=str_or_curie_or_uri, ontology_prefix=ontology_prefix, node=node
            )
        else:
            return None, None

    try:
        prefix, identifier = str_or_curie_or_uri.split(":", 1)
    except ValueError:  # skip nodes that don't look like normal CURIEs
        if str_or_curie_or_uri not in BAD_CURIES:
            BAD_CURIES.add(str_or_curie_or_uri)
            logger.debug(f"could not split CURIE on colon: {str_or_curie_or_uri}")
        return None, None

    norm_node_prefix = bioregistry.normalize_prefix(prefix)
    if norm_node_prefix:
        identifier = bioregistry.standardize_identifier(norm_node_prefix, identifier)
        return ReferenceTuple(norm_node_prefix, identifier)
    elif strict:
        raise MissingPrefixError(
            curie=str_or_curie_or_uri, ontology_prefix=ontology_prefix, node=node
        )
    else:
        return None, None


def _parse_iri(iri: str) -> ReferenceTuple | None:
    """Parse an IRI into a reference, if possible."""
    p, i = bioregistry.parse_iri(iri)
    if p and i:
        return ReferenceTuple(p, i)
    return None


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
