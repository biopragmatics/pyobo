# -*- coding: utf-8 -*-

"""Utilities for generating OBO content."""

from typing import Any, List, Mapping

import networkx as nx

from .. import TypeDef
from ..struct import Reference, Term

__all__ = [
    'get_terms_from_graph',
    'from_species',
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


from_species = TypeDef(
    id='from_species',
    name='from species',
)
