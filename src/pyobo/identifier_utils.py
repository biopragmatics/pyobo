# -*- coding: utf-8 -*-

"""Utilities for handling prefixes."""

import hashlib
import logging
from collections import defaultdict
from functools import wraps
from typing import Optional, Tuple, Union

import bioregistry
from bioregistry.external import get_miriam

from .registries import (
    get_prefix_to_miriam_prefix, get_prefix_to_obofoundry_prefix, get_prefix_to_ols_prefix,
    get_remappings_prefix, get_xrefs_blacklist, get_xrefs_prefix_blacklist, get_xrefs_suffix_blacklist,
)

__all__ = [
    'normalize_curie',
    'get_identifiers_org_link',
    'normalize_prefix',
    'normalize_dashes',
    'hash_curie',
    'wrap_norm_prefix',
]

logger = logging.getLogger(__name__)


def alternate_strip_prefix(s, prefix):
    _prefix_colon = f'{prefix.lower()}:'
    if s.lower().startswith(_prefix_colon):
        s = s[len(_prefix_colon):]
    return s


UBERON_UNHANDLED = defaultdict(list)
MIRIAM = get_miriam(mappify=True)


class MissingPrefix(ValueError):
    """Raised on a missing prefix."""

    def __init__(self, prefix, curie, xref=None, ontology=None):
        self.prefix = prefix
        self.curie = curie
        self.xref = xref
        self.ontology = ontology

    def __str__(self) -> str:
        s = ''
        if self.ontology:
            s += f'[{self.ontology}] '
        s += f'unhandled prefix {self.prefix} found in curie {self.curie}'
        if self.xref:
            s += f'/xref {self.xref}'
        return s


def normalize_prefix(prefix: str, *, curie=None, xref=None) -> Optional[str]:
    """Normalize a namespace and return, if possible."""
    norm_prefix = bioregistry.normalize_prefix(prefix)
    if norm_prefix is not None:
        return norm_prefix

    if curie is None or curie.startswith('obo:'):
        return
    if curie.startswith('UBERON:'):  # uberon has tons of xrefs to anatomical features. skip them
        UBERON_UNHANDLED[prefix].append((curie, xref))
    else:
        raise MissingPrefix(prefix=prefix, curie=curie, xref=xref)


def normalize_curie(node: str) -> Union[Tuple[str, str], Tuple[None, None]]:
    """Parse a string that looks like a CURIE.

    - Normalizes the namespace
    - Checks against a blacklist for the entire curie, for the namespace, and for suffixes.
    """
    if node in get_xrefs_blacklist():
        return None, None
    # Skip node if it has a blacklisted prefix
    for blacklisted_prefix in get_xrefs_prefix_blacklist():
        if node.startswith(blacklisted_prefix):
            return None, None
    # Skip node if it has a blacklisted suffix
    for suffix in get_xrefs_suffix_blacklist():
        if node.endswith(suffix):
            return None, None
    # Remap node's prefix (if necessary)
    for old_prefix, new_prefix in get_remappings_prefix().items():
        if node.startswith(old_prefix):
            node = new_prefix + ':' + node[len(old_prefix):]

    try:
        head_ns, identifier = node.split(':', 1)
    except ValueError:  # skip nodes that don't look like normal CURIEs
        # logger.info(f'skipping: {node}')
        return None, None

    norm_node_prefix = normalize_prefix(head_ns, curie=node)
    if not norm_node_prefix:
        return None, None
    return norm_node_prefix, identifier


def get_identifiers_org_link(prefix: str, identifier: str) -> Optional[str]:
    """Get the identifiers.org URL if possible."""
    miriam_prefix, namespace_in_lui = get_prefix_to_miriam_prefix().get(prefix, (None, None))
    if not miriam_prefix and prefix in MIRIAM:
        miriam_prefix = prefix
        namespace_in_lui = MIRIAM[prefix]['namespaceEmbeddedInLui']
    if not miriam_prefix:
        return
    if namespace_in_lui:
        miriam_prefix = miriam_prefix.upper()
    return f'https://identifiers.org/{miriam_prefix}:{identifier}'


def get_obofoundry_link(prefix: str, identifier: str) -> Optional[str]:
    """Get the OBO Foundry URL if possible."""
    obo_prefix = get_prefix_to_obofoundry_prefix().get(prefix)
    return f'http://purl.obolibrary.org/obo/{obo_prefix.upper()}_{identifier}'


def get_ols_link(prefix: str, identifier: str) -> Optional[str]:
    """Get the OLS URL if possible."""
    ols_prefix = get_prefix_to_ols_prefix().get(prefix)
    if ols_prefix is None:
        return
    obo_link = get_obofoundry_link(prefix, identifier)
    if obo_link is not None:
        return f'https://www.ebi.ac.uk/ols/ontologies/{ols_prefix}/terms?iri={obo_link}'


# See: https://en.wikipedia.org/wiki/Dash
FIGURE_DASH = b'\xe2\x80\x92'.decode('utf-8')
EN_DASH = b'\xe2\x80\x93'.decode('utf-8')
EM_DASH = b'\xe2\x80\x94'.decode('utf-8')
HORIZONAL_BAR = b'\xe2\x80\x95'.decode('utf-8')
NORMAL_DASH = '-'


def normalize_dashes(s: str) -> str:
    """Normalize dashes in a string."""
    return s. \
        replace(FIGURE_DASH, NORMAL_DASH). \
        replace(EN_DASH, NORMAL_DASH). \
        replace(EM_DASH, NORMAL_DASH). \
        replace(HORIZONAL_BAR, NORMAL_DASH)


def hash_curie(prefix, identifier) -> str:
    """Hash a curie with MD5."""
    return hashlib.md5(f'{prefix}:{identifier}'.encode('utf-8')).hexdigest()  # noqa:S303


def wrap_norm_prefix(f):
    """Decorate a function that take in a prefix to auto-normalize, or return None if it can't be normalized."""

    @wraps(f)
    def _wrapped(prefix, *args, **kwargs):
        norm_prefix = normalize_prefix(prefix)
        if norm_prefix is None:
            raise ValueError(f'Invalid prefix: {prefix}')
        return f(norm_prefix, *args, **kwargs)

    return _wrapped
