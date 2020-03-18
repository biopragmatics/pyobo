# -*- coding: utf-8 -*-

"""Utilities for extracting synonyms."""

import logging
from typing import Iterable, List, Mapping, Tuple

import networkx as nx

from ..cache_utils import cached_multidict
from ..getters import get_obo_graph
from ..graph_utils import iterate_obo_nodes
from ..io_utils import multidict
from ..path_utils import prefix_directory_join

__all__ = [
    'get_synonyms',
]

logger = logging.getLogger(__name__)


def get_synonyms(prefix: str, **kwargs) -> Mapping[str, List[str]]:
    """Get the OBO file and output a synonym dictionary."""
    path = prefix_directory_join(prefix, f"{prefix}_synonyms.tsv")
    header = [f'{prefix}_id', 'synonym']

    @cached_multidict(path=path, header=header)
    def _get_multidict() -> Mapping[str, List[str]]:
        graph = get_obo_graph(prefix, **kwargs)
        rv = multidict(_iterate(graph=graph, prefix=prefix))
        return {
            k: sorted(set(v))
            for k, v in rv.items()
        }

    return _get_multidict()


def _iterate(graph: nx.MultiDiGraph, prefix: str) -> Iterable[Tuple[str, str]]:
    for identifier, data in iterate_obo_nodes(graph=graph, prefix=prefix, skip_external=True):
        name = data['name']
        yield identifier, name

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
                logger.warning(f'For {identifier} unhandled synonym: {synonym}')
                continue

            yield identifier, synonym
