# -*- coding: utf-8 -*-

"""Utilities for handling prefixes."""

import logging
from functools import wraps
from typing import Optional, Tuple, Union

import bioregistry

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


class MissingPrefix(ValueError):
    """Raised on a missing prefix."""

    def __init__(self, prefix, curie, xref=None, ontology=None):
        self.prefix = prefix
        self.curie = curie
        self.xref = xref
        self.ontology = ontology
        self.reference = None

    def __str__(self) -> str:
        s = ""
        if self.ontology:
            s += f"[{self.ontology}] "
        s += f"unhandled prefix {self.prefix} found in curie {self.curie}"
        if self.xref:
            s += f"/xref {self.xref}"
        if self.reference is not None:
            s += f" from {self.reference.curie}"
        return s


def _normalize_prefix(prefix: str, *, curie=None, xref=None, strict: bool = True) -> Optional[str]:
    """Normalize a namespace and return, if possible."""
    norm_prefix = bioregistry.normalize_prefix(prefix)
    if norm_prefix is not None:
        return norm_prefix
    elif strict:
        raise MissingPrefix(prefix=prefix, curie=curie, xref=xref)
    else:
        return None


BAD_CURIES = set()


def normalize_curie(
    curie: str, *, strict: bool = True
) -> Union[Tuple[str, str], Tuple[None, None]]:
    """Parse a string that looks like a CURIE.

    :param curie: A compact uniform resource identifier (CURIE)
    :param strict: Should an exception be thrown if the CURIE can not be parsed w.r.t. the Bioregistry?
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
    curie = remap_prefix(curie)

    try:
        head_ns, identifier = curie.split(":", 1)
    except ValueError:  # skip nodes that don't look like normal CURIEs
        if curie not in BAD_CURIES:
            BAD_CURIES.add(curie)
            logger.debug(f"could not split CURIE on colon: {curie}")
        return None, None

    # remove redundant prefix
    if identifier.casefold().startswith(f"{head_ns.casefold()}:"):
        identifier = identifier[len(head_ns) + 1 :]

    norm_node_prefix = _normalize_prefix(head_ns, curie=curie, strict=strict)
    if not norm_node_prefix:
        return None, None
    return norm_node_prefix, identifier


def wrap_norm_prefix(f):
    """Decorate a function that take in a prefix to auto-normalize, or return None if it can't be normalized."""

    @wraps(f)
    def _wrapped(prefix, *args, **kwargs):
        norm_prefix = bioregistry.normalize_prefix(prefix)
        if norm_prefix is None:
            raise ValueError(f"Invalid prefix: {prefix}")
        return f(norm_prefix, *args, **kwargs)

    return _wrapped


def standardize_ec(ec: str) -> str:
    """Standardize an EC code identifier by removing all trailing dashes and dots."""
    ec = ec.strip()
    for _ in range(4):
        ec = ec.rstrip("-").rstrip(".")
    return ec
