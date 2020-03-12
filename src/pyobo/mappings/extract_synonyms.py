# -*- coding: utf-8 -*-

"""Utilities for extracting synonyms."""

import logging
from typing import Iterable, List, Mapping, Optional, Tuple

import networkx as nx

from ..cache_utils import cached_multidict
from ..getters import get_obo_graph
from ..io_utils import multidict
from ..path_utils import prefix_directory_join

__all__ = [
    'get_synonyms',
]

logger = logging.getLogger(__name__)


def get_synonyms(prefix: str, url: Optional[str] = None) -> Mapping[str, List[str]]:
    """Get the OBO file and output a synonym dictionary."""
    path = prefix_directory_join(prefix, f"{prefix}_synonyms.tsv")
    header = [f'{prefix}_id', f'synonym']

    @cached_multidict(path=path, header=header)
    def _get_multidict() -> Mapping[str, List[str]]:
        graph = get_obo_graph(prefix, url=url)
        rv = multidict(_iterate(graph, prefix))
        return {
            k: sorted(set(v))
            for k, v in rv.items()
        }

    return _get_multidict()


def _iterate(graph: nx.MultiDiGraph, prefix: str) -> Iterable[Tuple[str, str]]:
    for node, data in graph.nodes(data=True):
        if not node.lower().startswith(f'{prefix.lower()}:'):
            continue

        name = data['name']
        yield node, name

        for synonym in data.get('synonym', []):
            synonym = synonym.strip('"')
            if not synonym:
                continue

            if "RELATED" in synonym:
                synonym = synonym[:synonym.index('RELATED')].rstrip().rstrip('"')
            elif "EXACT" in synonym:
                synonym = synonym[:synonym.index('EXACT')].rstrip().rstrip('"')
            elif "BROAD" in synonym:
                synonym = synonym[:synonym.index('BROAD')].rstrip().rstrip('"')
            else:
                logger.warning(f'For {node} unhandled synonym: {synonym}')
                continue

            yield node, synonym
