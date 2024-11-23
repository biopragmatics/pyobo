"""Utilities for handling prefixes."""

from __future__ import annotations

import logging
from functools import wraps
from typing import ClassVar

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
    "normalize_curie",
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


def normalize_curie(
    curie: str,
    *,
    strict: bool = True,
    ontology_prefix: str | None = None,
    node: Reference | None = None,
) -> tuple[str, str] | tuple[None, None]:
    """Parse a string that looks like a CURIE.

    :param curie: A compact uniform resource identifier (CURIE)
    :param strict: Should an exception be thrown if the CURIE can not be parsed w.r.t. the Bioregistry?
    :param ontology_prefix: The ontology in which the CURIE appears
    :return: A parse tuple or a tuple of None, None if not able to parse and not strict

    - Normalizes the namespace
    - Checks against a blacklist for the entire curie, for the namespace, and for suffixes.
    """
    # Remap the curie with the full list
    curie = remap_full(curie)

    # Remap node's prefix (if necessary)
    curie = remap_prefix(curie, ontology_prefix=ontology_prefix)

    if curie_is_blacklisted(curie):
        return None, None
    if curie_has_blacklisted_prefix(curie):
        return None, None
    if curie_has_blacklisted_suffix(curie):
        return None, None

    if curie.startswith("http:") or curie.startswith("https:"):
        if reference := parse_iri(curie):
            return reference.pair
        elif strict:
            raise UnparsableIRIError(curie=curie, ontology_prefix=ontology_prefix, node=node)
        else:
            return None, None

    try:
        prefix, identifier = curie.split(":", 1)
    except ValueError:  # skip nodes that don't look like normal CURIEs
        if curie not in BAD_CURIES:
            BAD_CURIES.add(curie)
            logger.debug(f"could not split CURIE on colon: {curie}")
        return None, None

    # remove redundant prefix
    if identifier.casefold().startswith(f"{prefix.casefold()}:"):
        identifier = identifier[len(prefix) + 1 :]

    norm_node_prefix = bioregistry.normalize_prefix(prefix)
    if norm_node_prefix:
        return norm_node_prefix, identifier
    elif strict:
        raise MissingPrefixError(curie=curie, ontology_prefix=ontology_prefix, node=node)
    else:
        return None, None


def parse_iri(iri: str) -> Reference | None:
    """Parse an IRI into a reference, if possible."""
    p, i = bioregistry.parse_iri(iri)
    if p and i:
        return Reference(prefix=p, identifier=i)
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
