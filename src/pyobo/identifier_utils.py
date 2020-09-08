# -*- coding: utf-8 -*-

"""Utilities for handling prefixes."""

import hashlib
import logging
from collections import defaultdict
from functools import wraps
from typing import Dict, Mapping, Optional, Tuple, Union

from .registries import (
    Resource, get_curated_registry_database, get_miriam, get_namespace_synonyms, get_obofoundry, get_obsolete,
    get_prefix_to_miriam_prefix, get_remappings_prefix, get_xrefs_blacklist, get_xrefs_prefix_blacklist,
    get_xrefs_suffix_blacklist,
)
from .registries.registries import _sample_graph

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


def normalize_prefix(prefix: str, *, curie=None, xref=None) -> Optional[str]:
    """Normalize a namespace and return, if possible."""
    for string_transformation in (lambda x: x, str.lower, str.upper, str.casefold):
        namespace_transformed = string_transformation(prefix)
        rv = get_namespace_synonyms().get(namespace_transformed)
        if rv is not None:
            return rv

    if curie is None or curie.startswith('obo:'):
        return
    if curie.startswith('UBERON:'):  # uberon has tons of xrefs to anatomical features. skip them
        UBERON_UNHANDLED[prefix].append((curie, xref))
    else:
        logger.warning('unhandled prefix %s found in curie %s/xref %s', prefix, curie, xref)


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
        if norm_prefix is not None:
            return f(norm_prefix, *args, **kwargs)

    return _wrapped


def get_metaregistry(try_new=False) -> Mapping[str, Resource]:
    """Get a combine registry."""
    rv: Dict[str, Resource] = {}

    synonym_to_prefix = {}
    for prefix, entry in get_curated_registry_database().items():
        if prefix in get_obsolete():
            continue
        synonym_to_prefix[prefix.lower()] = prefix

        title = entry.get('title')
        if title is not None:
            synonym_to_prefix[title.lower()] = prefix
        for synonym in entry.get("synonyms", {}):
            synonym_to_prefix[synonym.lower()] = prefix

    for entry in get_miriam():
        prefix = normalize_prefix(entry['prefix'])
        if prefix is None:
            prefix = entry['prefix']
            logger.debug(f'Could not look up MIRIAM prefix: {prefix}')
        if prefix in get_obsolete():
            continue
        rv[prefix] = Resource(
            name=entry['name'],
            prefix=prefix,
            pattern=entry['pattern'],
            miriam_id=entry['mirId'],
            # namespace_in_pattern=namespace['namespaceEmbeddedInLui'],
        )

    for entry in sorted(get_obofoundry(), key=lambda x: x['id'].lower()):
        prefix = normalize_prefix(entry['id'])
        if prefix is None:
            prefix = entry['id']
            logger.debug(f'Could not look up OBO prefix: {prefix}')
        is_obsolete = entry.get('is_obsolete') or prefix in get_obsolete()
        already_found = prefix in rv
        if already_found:
            if is_obsolete:
                del rv[prefix]
            else:
                rv[prefix].obofoundry_id = prefix
            continue
        elif is_obsolete:
            continue

        title = entry['title']
        prefix = synonym_to_prefix.get(prefix, prefix)
        curated_info = get_curated_registry_database().get(prefix)
        if curated_info and 'pattern' in curated_info:
            # namespace_in_pattern = curated_registry.get('namespace_in_pattern')
            rv[prefix] = Resource(
                name=title,
                prefix=prefix,
                pattern=curated_info['pattern'],
                # namespace_in_pattern=namespace_in_pattern,
            )
            continue

        if not try_new:
            continue

        if not curated_info:
            print(f'missing curated pattern for {prefix}')
            leng = _sample_graph(prefix)
            if leng:
                print(f'"{prefix}": {{\n   "pattern": "\\\\d{{{leng}}}"\n}},')
            continue
        if curated_info.get('not_available_as_obo') or curated_info.get('no_own_terms'):
            continue

    for prefix, entry in get_curated_registry_database().items():
        if prefix in rv:
            continue
        title = entry.get('title')
        if not title:
            logger.debug('No title for %s', prefix)
            title = prefix
        pattern = entry.get('pattern')
        if not title or not pattern:
            continue
        rv[prefix] = Resource(
            name=title,
            prefix=prefix,
            pattern=pattern,
        )

        # print(f'unhandled {prefix}')
    return rv
