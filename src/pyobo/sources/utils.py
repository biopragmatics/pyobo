# -*- coding: utf-8 -*-

"""Utilities for generating OBO content."""

import gzip
import logging
import time
from typing import Any, List, Mapping
from xml.etree import ElementTree
from xml.etree.ElementTree import Element

import networkx as nx

from .. import TypeDef
from ..struct import Reference, Term

__all__ = [
    'get_terms_from_graph',
    'from_species',
    'parse_xml_gz',
]

logger = logging.getLogger(__name__)


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


def parse_xml_gz(path: str) -> Element:
    """Parse an XML file from a path to a GZIP file."""
    t = time.time()
    logger.info('parsing xml from %s', path)
    with gzip.open(path) as file:
        tree = ElementTree.parse(file)
    logger.info('parsed xml in %.2f seconds', time.time() - t)
    return tree.getroot()
