# -*- coding: utf-8 -*-

"""Parser functions for OBO documents."""

from typing import Any, List, Mapping

import networkx as nx

from .struct import Reference, Term

__all__ = [
    'get_terms_from_graph',
]


def get_terms_from_graph(graph: nx.Graph) -> List[Term]:
    """Get all of the terms from a OBO graph."""
    ontology = graph.graph['ontology']

    #: Identifiers to references
    references = {
        node: Reference(prefix=ontology, identifier=node, name=data['name'])
        for node, data in graph.nodes(data=True)
    }

    def _make_term(node: str, data: Mapping[str, Any]) -> Term:
        reference = references[node]
        return Term(
            reference=reference,
            name=reference.name,
            definition=data['def'],
            parents=list(_get_parents(data)),
        )

    def _get_parents(data: Mapping[str, Any]):
        for parent in data.get('is_a', []):
            # May have to add more logic here later
            yield references[parent]

    terms = []
    for node, data in graph.nodes(data=True):
        term = _make_term(node, data)
        terms.append(term)

    return terms
