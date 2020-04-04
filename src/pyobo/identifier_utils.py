# -*- coding: utf-8 -*-

"""Utilities for handling prefixes."""

__all__ = [
    'normalize_curie',
    'normalize_prefix',
]

from collections import defaultdict
from typing import Optional, Tuple, Union

from .registries import get_curated_registry, get_namespace_synonyms


def alternate_strip_prefix(s, prefix):
    _prefix_colon = f'{prefix.lower()}:'
    if s.lower().startswith(_prefix_colon):
        s = s[len(_prefix_colon):]
    return s


SYNONYM_TO_KEY = get_namespace_synonyms()
UNHANDLED_NAMESPACES = defaultdict(list)
UBERON_UNHANDLED = defaultdict(list)


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


METAREGISTRY = get_curated_registry()

#: Xrefs starting with these prefixes will be ignored
XREF_PREFIX_BLACKLIST = set(METAREGISTRY['blacklists']['prefix'])
XREF_SUFFIX_BLACKLIST = set(METAREGISTRY['blacklists']['suffix'])
#: Xrefs matching these will be ignored
XREF_BLACKLIST = set(METAREGISTRY['blacklists']['full'])

PREFIX_REMAP = METAREGISTRY['remappings']['prefix']

ALLOWED_UNNORM = set(METAREGISTRY['database'])

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
    for old_prefix, new_prefix in PREFIX_REMAP.items():
        old_prefix_colon = f'{old_prefix}:'
        if node.startswith(old_prefix_colon):
            node = new_prefix + ':' + node[len(old_prefix_colon):]

    try:
        head_ns, identifier = node.split(':', 1)
    except ValueError:  # skip nodes that don't look like normal CURIEs
        # logger.info(f'skipping: {node}')
        return None, None

    norm_node_prefix = normalize_prefix(head_ns, curie=node)
    if not norm_node_prefix:
        return None, None
    return norm_node_prefix, identifier
