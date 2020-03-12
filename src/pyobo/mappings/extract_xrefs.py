# -*- coding: utf-8 -*-

"""Utilities for extracting xrefs."""

import logging
import os
from collections import defaultdict
from typing import Iterable, List, Mapping, Optional, Tuple

import networkx as nx
import pandas as pd
from tqdm import tqdm

from ..getters import get_obo_graph
from ..io_utils import multidict, open_multimap_tsv, write_multimap_tsv
from ..path_utils import prefix_directory_join
from ..registries import get_curated_registry, get_namespace_synonyms

__all__ = [
    'iterate_xrefs_from_graph',
    'get_xrefs',
    'get_all_xrefs',
]

logger = logging.getLogger(__name__)

HERE = os.path.abspath(os.path.dirname(__file__))

METAREGISTRY = get_curated_registry()

#: Xrefs starting with these prefixes will be ignored
XREF_PREFIX_BLACKLIST = set(METAREGISTRY['blacklists']['prefix'])
XREF_SUFFIX_BLACKLIST = set(METAREGISTRY['blacklists']['suffix'])
#: Xrefs matching these will be ignored
XREF_BLACKLIST = set(METAREGISTRY['blacklists']['full'])

PREFIX_REMAP = METAREGISTRY['remappings']['prefix']

ALLOWED_UNNORM = set(METAREGISTRY['database'])

SYNONYM_TO_KEY = get_namespace_synonyms()
UNHANDLED_NAMESPACES = defaultdict(list)
UBERON_UNHANDLED = defaultdict(list)


def get_all_xrefs(prefix: str, url: Optional[str] = None) -> pd.DataFrame:
    """Get all xrefs."""
    path = prefix_directory_join(prefix, f"{prefix}_mappings.tsv")
    if os.path.exists(path):
        logger.debug('loading %s xrefs', prefix, path)
        return pd.read_csv(path, sep='\t', dtype={
            'source_ns': str, 'source_id': str, 'xref_ns': str, 'xref_id': str,
        })

    graph = get_obo_graph(prefix, url=url)

    logger.info('writing %s mapping to %s', prefix, path)
    df = pd.DataFrame(
        list(iterate_xrefs_from_graph(graph)),
        columns=['source_ns', 'source_id', 'target_ns', 'target_id'],
    )

    df.to_csv(path, sep='\t', index=False)
    return df


def get_xrefs(prefix: str, xref_prefix: str, url: Optional[str] = None) -> Mapping[str, List[str]]:
    """Get xrefs to a given target."""
    path = prefix_directory_join(prefix, f"{prefix}_{xref_prefix}_mappings.tsv")
    if os.path.exists(path):
        logger.debug('loading %s xrefs to %s from %s', prefix, xref_prefix, path)
        return open_multimap_tsv(path)

    graph = get_obo_graph(prefix, url=url)

    rv = multidict(
        (head_id, xref_id)
        for head_ns, head_id, xref_ns, xref_id in iterate_xrefs_from_graph(graph)
        if head_ns == prefix and xref_ns == xref_prefix
    )

    logger.info('writing %s mapping to %s', prefix, path)
    write_multimap_tsv(path=path, header=[f'{prefix}_id', f'{xref_prefix}_id'], rv=rv)

    return rv


def iterate_xrefs_from_graph(graph: nx.Graph, use_tqdm: bool = True) -> Iterable[Tuple[str, str, str, str]]:
    """Iterate over cross references in the graph."""
    it = graph.nodes(data=True)
    if use_tqdm:
        it = tqdm(it, desc=f'Extracting xrefs from {graph}')
    for node, data in it:
        node = node.strip()

        if node in XREF_BLACKLIST:
            continue

        # Skip node if it has a blacklisted prefix
        for prefix in XREF_PREFIX_BLACKLIST:
            if node.startswith(prefix):
                continue

        # Skip node if it has a blacklisted suffix
        for suffix in XREF_SUFFIX_BLACKLIST:
            if node.endswith(suffix):
                continue

        # Remap node's prefix (if necessary)
        for prefix, new_prefix in PREFIX_REMAP.items():
            if node.startswith(prefix):
                node = new_prefix + node[len(prefix):]

        try:
            head_ns, head_id = node.split(':', 1)
        except ValueError:  # skip nodes that don't look like normal CURIEs
            # logger.info(f'skipping: {node}')
            continue

        norm_head_ns = normalize_namespace(head_ns, node, None)
        if not norm_head_ns:
            continue

        # TODO check if synonyms are also written like CURIEs,
        # ... not that they should be

        for xref in data.get('xref', []):
            xref = xref.strip()

            if (
                node == xref
                or any(xref.startswith(x) for x in XREF_PREFIX_BLACKLIST)
                or xref in XREF_BLACKLIST
                or ':' not in xref
            ):
                continue  # sometimes xref to self... weird

            for prefix, new_prefix in PREFIX_REMAP.items():
                if xref.startswith(prefix):
                    xref = new_prefix + xref[len(prefix):]

            split_space = ' ' in xref
            if split_space:
                _xref_split = xref.split(' ', 1)
                if _xref_split[1][0] not in {'"', '('}:
                    logger.warning(f'Problem with space in xref {node} {xref}')
                    continue
                xref = _xref_split[0]

            try:
                xref_ns, xref_id = xref.split(':', 1)
            except ValueError:
                if split_space:
                    logger.warning(f'problem splitting after space split {node} {xref}')
                else:
                    logger.warning(f'problem splitting {node} {xref}')

                continue

            norm_xref_ns = normalize_namespace(xref_ns, node, xref)
            if not norm_xref_ns:
                continue

            yield norm_head_ns, head_id, norm_xref_ns, xref_id


def normalize_namespace(namespace: str, curie: str, xref=None) -> Optional[str]:
    """Normalize a namespace and return, if possible."""
    for string_transformation in (lambda x: x, str.lower, str.upper, str.casefold):
        namespace_transformed = string_transformation(namespace)
        if namespace_transformed in SYNONYM_TO_KEY:
            return SYNONYM_TO_KEY[namespace_transformed]

    if curie.startswith('UBERON:'):  # uberon has tons of xrefs to anatomical features. skip them
        UBERON_UNHANDLED[namespace].append((curie, xref))
    else:
        UNHANDLED_NAMESPACES[namespace].append((curie, xref))
