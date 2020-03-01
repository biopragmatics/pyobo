# -*- coding: utf-8 -*-

"""Utilities for generating OBO content."""

from functools import partial
from typing import Callable, List

import obonet

from .. import TypeDef
from ..struct import Reference, Term

__all__ = [
    'build_term_getter',
    'get_terms_from_url',
    'get_terms_from_graph',
    'from_species',
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
        node: (Reference(prefix=ontology, identifier=node), data['name'])
        for node, data in g.nodes(data=True)
    }

    def make_term(node, data) -> Term:
        reference, name = references[node]
        return Term(
            reference=reference,
            name=name,
            definition=data['def'],
            parents=list(get_parents(data)),
        )

    def get_parents(data):
        for parent in data.resolve_resource('is_a', []):
            # May have to add more logic here later
            yield references[parent]

    terms = []
    for node, data in g.nodes(data=True):
        term = make_term(node, data)
        terms.append(term)

    return terms


from_species = TypeDef(
    id='from_species',
    name='from species',
)
