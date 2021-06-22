# -*- coding: utf-8 -*-

"""Utilities for handling prefixes."""

import logging
from collections import defaultdict
from functools import wraps
from typing import Optional, Tuple, Union

import bioregistry

from .registries import (
    get_remappings_prefix,
    get_xrefs_blacklist,
    get_xrefs_prefix_blacklist,
    get_xrefs_suffix_blacklist,
    remap_full,
)

__all__ = [
    "normalize_curie",
    "normalize_prefix",
    "wrap_norm_prefix",
]

logger = logging.getLogger(__name__)


def alternate_strip_prefix(s, prefix):
    _prefix_colon = f"{prefix.lower()}:"
    if s.lower().startswith(_prefix_colon):
        s = s[len(_prefix_colon) :]
    return s


UBERON_UNHANDLED = defaultdict(list)


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


def normalize_prefix(prefix: str, *, curie=None, xref=None, strict: bool = True) -> Optional[str]:
    """Normalize a namespace and return, if possible."""
    norm_prefix = bioregistry.normalize_prefix(prefix)
    if norm_prefix is not None:
        return norm_prefix

    if curie is None or curie.startswith("obo:"):
        return
    if curie.startswith("UBERON:"):  # uberon has tons of xrefs to anatomical features. skip them
        UBERON_UNHANDLED[prefix].append((curie, xref))
    elif strict:
        raise MissingPrefix(prefix=prefix, curie=curie, xref=xref)
    # if prefix.replace(':', '').replace("'", '').replace('-', '').replace('%27', '').isalpha():
    #     return  # skip if its just text


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
    if curie in get_xrefs_blacklist():
        return None, None
    # Skip node if it has a blacklisted prefix
    for blacklisted_prefix in get_xrefs_prefix_blacklist():
        if curie.startswith(blacklisted_prefix):
            return None, None
    # Skip node if it has a blacklisted suffix
    for suffix in get_xrefs_suffix_blacklist():
        if curie.endswith(suffix):
            return None, None

    # Remap the curie with the full list
    curie = remap_full(curie)

    # Remap node's prefix (if necessary)
    for old_prefix, new_prefix in get_remappings_prefix().items():
        if curie.startswith(old_prefix):
            curie = new_prefix + curie[len(old_prefix) :]

    try:
        head_ns, identifier = curie.split(":", 1)
    except ValueError:  # skip nodes that don't look like normal CURIEs
        logger.debug(f"could not split CURIE on colon: {curie}")
        return None, None

    # remove redundant prefix
    if identifier.casefold().startswith(f"{head_ns.casefold()}:"):
        identifier = identifier[len(head_ns) + 1 :]

    norm_node_prefix = normalize_prefix(head_ns, curie=curie, strict=strict)
    if not norm_node_prefix:
        return None, None
    return norm_node_prefix, identifier


def wrap_norm_prefix(f):
    """Decorate a function that take in a prefix to auto-normalize, or return None if it can't be normalized."""

    @wraps(f)
    def _wrapped(prefix, *args, **kwargs):
        norm_prefix = normalize_prefix(prefix, strict=True)
        if norm_prefix is None:
            raise ValueError(f"Invalid prefix: {prefix}")
        return f(norm_prefix, *args, **kwargs)

    return _wrapped
