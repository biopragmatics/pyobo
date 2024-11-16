"""Utilities for handling prefixes."""

from __future__ import annotations

import logging
from functools import wraps

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
    "wrap_norm_prefix",
    "standardize_ec",
]

logger = logging.getLogger(__name__)


class MissingPrefixError(ValueError):
    """Raised on a missing prefix."""

    reference: Reference | None

    def __init__(
        self,
        *,
        curie: str,
        ontology: str | None = None,
        reference: Reference | None = None,
    ):
        """Initialize the error."""
        self.curie = curie
        self.ontology = ontology
        self.reference = reference

    def __str__(self) -> str:
        s = ""
        if self.ontology:
            s += f"[{self.ontology}] "
        s += f"curie contains unhandled prefix: `{self.curie}`"
        if self.reference is not None:
            s += f" from {self.reference.curie}"
        return s


BAD_CURIES: set[str] = set()


def normalize_curie(
    curie: str,
    *,
    strict: bool = True,
    ontology: str | None = None,
    reference_node: Reference | None = None,
) -> tuple[str, str] | tuple[None, None]:
    """Parse a string that looks like a CURIE.

    :param curie: A compact uniform resource identifier (CURIE)
    :param strict: Should an exception be thrown if the CURIE can not be parsed w.r.t. the Bioregistry?
    :param ontology: The ontology in which the CURIE appears
    :return: A parse tuple or a tuple of None, None if not able to parse and not strict

    - Normalizes the namespace
    - Checks against a blacklist for the entire curie, for the namespace, and for suffixes.
    """
    if curie_is_blacklisted(curie):
        return None, None
    if curie_has_blacklisted_prefix(curie):
        return None, None
    if curie_has_blacklisted_suffix(curie):
        return None, None

    # Remap the curie with the full list
    curie = remap_full(curie)

    # Remap node's prefix (if necessary)
    curie = remap_prefix(curie, ontology_prefix=ontology)

    # TODO reuse bioregistry logic for standardizing and parsing CURIEs?
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
    if norm_node_prefix is not None:
        return norm_node_prefix, identifier
    elif strict:
        raise MissingPrefixError(curie=curie, ontology=ontology, reference=reference_node)
    else:
        return None, None


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
