# -*- coding: utf-8 -*-

"""Utilities for extracting xrefs."""

import logging
import os
from collections import defaultdict
from typing import Iterable, Mapping, Optional, Tuple

import networkx as nx
import pandas as pd
from tqdm import tqdm

from ..cache_utils import cached_df, cached_mapping
from ..getters import get_obo_graph
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


def get_all_xrefs(prefix: str, **kwargs) -> pd.DataFrame:
    """Get all xrefs."""
    path = prefix_directory_join(prefix, f"{prefix}_mappings.tsv")
    dtype = {
        'source_ns': str, 'source_id': str, 'xref_ns': str, 'xref_id': str,
    }

    @cached_df(path=path, dtype=dtype)
    def _df_getter() -> pd.DataFrame:
        graph = get_obo_graph(prefix, **kwargs)
        logger.info('writing %s mapping to %s', prefix, path)
        return pd.DataFrame(
            list(iterate_xrefs_from_graph(graph)),
            columns=['source_ns', 'source_id', 'target_ns', 'target_id'],
        )

    return _df_getter()


def get_xrefs(prefix: str, xref_prefix: str, **kwargs) -> Mapping[str, str]:
    """Get xrefs to a given target."""
    path = prefix_directory_join(prefix, f"{prefix}_{xref_prefix}_mappings.tsv")
    header = [f'{prefix}_id', f'{xref_prefix}_id']

    @cached_mapping(path=path, header=header)
    def _get_mapping() -> Mapping[str, str]:
        graph = get_obo_graph(prefix, **kwargs)
        return dict(iterate_xrefs_filtered(graph, prefix, xref_prefix))

    return _get_mapping()


def iterate_xrefs_filtered(graph, p1, p2, use_tqdm: bool = True) -> Iterable[Tuple[str, str]]:
    """Iterate over cross references between the two namespaces in the graph."""
    for head_ns, head_id, xref_ns, xref_id in iterate_xrefs_from_graph(graph, use_tqdm=use_tqdm):
        if (head_ns == p1 and xref_ns == p2) or (head_ns == p2 and xref_ns == p1):
            yield head_id, xref_id


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
        for blacklisted_prefix in XREF_PREFIX_BLACKLIST:
            if node.startswith(blacklisted_prefix):
                continue

        # Skip node if it has a blacklisted suffix
        for suffix in XREF_SUFFIX_BLACKLIST:
            if node.endswith(suffix):
                continue

        # Remap node's prefix (if necessary)
        for old_prefix, new_prefix in PREFIX_REMAP.items():
            old_prefix_colon = f'{old_prefix}:'
            if node.startswith(old_prefix_colon):
                node = new_prefix + ':' + node[len(old_prefix_colon):]

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

            for blacklisted_prefix, new_prefix in PREFIX_REMAP.items():
                if xref.startswith(blacklisted_prefix):
                    xref = new_prefix + xref[len(blacklisted_prefix):]

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
