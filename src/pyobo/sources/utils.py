# -*- coding: utf-8 -*-

"""Utilities for generating OBO content."""

from functools import partial
from typing import Callable, List

import obonet

from ..struct import Reference, Term, Obo

__all__ = [
    'build_term_getter',
    'get_terms_from_url',
    'get_terms_from_graph',
]


def build_term_getter(url) -> Callable[[], List[Term]]:
    return partial(get_terms_from_url, url)


def get_terms_from_url(url: str) -> List[Term]:
    g = obonet.read_obo(url)
    return get_terms_from_graph(g)


def get_terms_from_graph(g) -> List[Term]:
    ontology = g.graph['ontology']

    #: Identifiers to references
    references = {
        node: Reference(
            namespace=ontology,
            identifier=node,
            name=data['name'],
        )
        for node, data in g.nodes(data=True)
    }

    def make_term(node, data) -> Term:
        return Term(
            reference=references[node],
            definition=data['def'],
            parents=list(get_parents(data)),
        )

    def get_parents(data):
        for parent in data.get('is_a', []):
            # May have to add more logic here later
            yield references[parent]

    terms = []
    for node, data in g.nodes(data=True):
        term = make_term(node, data)
        terms.append(term)

    return terms
