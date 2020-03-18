# -*- coding: utf-8 -*-

"""Graph utilities."""

from typing import Any, Iterable, Mapping, Tuple

import networkx as nx

__all__ = [
    'iterate_obo_nodes',
]


def iterate_obo_nodes(
    prefix: str,
    graph: nx.MultiDiGraph,
    skip_external: bool = False,
) -> Iterable[Tuple[str, Mapping[str, Any]]]:
    """Iterate over the nodes in the graph with the prefix stripped (if it's there)."""
    for node, data in graph.nodes(data=True):
        _prefix_colon = f'{prefix.lower()}:'
        if node.lower().startswith(_prefix_colon):
            node = node[len(_prefix_colon):]
        elif skip_external:
            continue
        yield node, data
