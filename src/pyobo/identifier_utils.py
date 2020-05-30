# -*- coding: utf-8 -*-

"""Utilities for handling prefixes."""

import logging
from collections import defaultdict
from typing import Optional, Tuple, Union

from .registries import (
    PREFIX_TO_MIRIAM_PREFIX, REMAPPINGS_PREFIX, XREF_BLACKLIST, XREF_PREFIX_BLACKLIST, XREF_SUFFIX_BLACKLIST,
    get_miriam, get_namespace_synonyms,
)

__all__ = [
    'normalize_curie',
    'get_identifiers_org_link',
    'normalize_prefix',
    'normalize_dashes',
]

logger = logging.getLogger(__name__)


def alternate_strip_prefix(s, prefix):
    _prefix_colon = f'{prefix.lower()}:'
    if s.lower().startswith(_prefix_colon):
        s = s[len(_prefix_colon):]
    return s


SYNONYM_TO_KEY = get_namespace_synonyms()
UNHANDLED_NAMESPACES = defaultdict(list)
UBERON_UNHANDLED = defaultdict(list)
MIRIAM = get_miriam(mappify=True)


def normalize_prefix(prefix: str, *, curie=None, xref=None) -> Optional[str]:
    """Normalize a namespace and return, if possible."""
    for string_transformation in (lambda x: x, str.lower, str.upper, str.casefold):
        namespace_transformed = string_transformation(prefix)
        if namespace_transformed in SYNONYM_TO_KEY:
            return SYNONYM_TO_KEY[namespace_transformed]

    if curie is None:
        return
    if curie.startswith('UBERON:'):  # uberon has tons of xrefs to anatomical features. skip them
        UBERON_UNHANDLED[prefix].append((curie, xref))
    else:
        UNHANDLED_NAMESPACES[prefix].append((curie, xref))


COLUMNS = ['source_ns', 'source_id', 'target_ns', 'target_id']


def normalize_curie(node: str) -> Union[Tuple[str, str], Tuple[None, None]]:
    """Parse a string that looks like a CURIE.

    - Normalizes the namespace
    - Checks against a blacklist for the entire curie, for the namespace, and for suffixes.
    """
    if node in XREF_BLACKLIST:
        return None, None
    # Skip node if it has a blacklisted prefix
    for blacklisted_prefix in XREF_PREFIX_BLACKLIST:
        if node.startswith(blacklisted_prefix):
            return None, None
    # Skip node if it has a blacklisted suffix
    for suffix in XREF_SUFFIX_BLACKLIST:
        if node.endswith(suffix):
            return None, None
    # Remap node's prefix (if necessary)
    for old_prefix, new_prefix in REMAPPINGS_PREFIX.items():
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
    miriam_prefix, namespace_in_lui = PREFIX_TO_MIRIAM_PREFIX.get(prefix, (None, None))
    if not miriam_prefix and prefix in MIRIAM:
        miriam_prefix = prefix
        namespace_in_lui = MIRIAM[prefix]['namespaceEmbeddedInLui']
    if not miriam_prefix:
        return
    if namespace_in_lui:
        miriam_prefix = miriam_prefix.upper()
    return f'https://identifiers.org/{miriam_prefix}:{identifier}'


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
