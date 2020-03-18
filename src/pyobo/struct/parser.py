# -*- coding: utf-8 -*-

"""Parser functions for OBO documents."""

from typing import Any, Iterable, List, Mapping

import networkx as nx

from .struct import Reference, Term
from ..graph_utils import iterate_obo_nodes

__all__ = [
    'get_terms_from_graph',
]


def get_terms_from_graph(graph: nx.MultiDiGraph) -> List[Term]:
    """Get all of the terms from a OBO graph."""
    prefix = graph.graph['ontology']

    #: Identifiers to references
    references = {
        identifier: Reference(prefix=prefix, identifier=identifier, name=data['name'])
        for identifier, data in iterate_obo_nodes(graph=graph, prefix=prefix)
    }

    def _make_term(_identifier: str, _data: Mapping[str, Any]) -> Term:
        reference = references[_identifier]
        return Term(
            reference=reference,
            definition=_data['def'],
            parents=list(_get_parents(_data)),
        )

    def _get_parents(_data: Mapping[str, Any]) -> Iterable[Reference]:
        for parent in _data.get('is_a', []):
            # May have to add more logic here later
            yield references[parent]

    return [
        _make_term(identifier, data)
        for identifier, data in iterate_obo_nodes(graph=graph, prefix=prefix)
    ]
