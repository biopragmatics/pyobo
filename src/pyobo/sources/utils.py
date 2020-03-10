# -*- coding: utf-8 -*-

"""Utilities for generating OBO content."""

import gzip
import logging
import os
import time
from importlib import import_module
from typing import Any, Iterable, List, Mapping
from xml.etree import ElementTree
from xml.etree.ElementTree import Element

import networkx as nx

from .. import TypeDef
from ..struct import Obo, Reference, Term

__all__ = [
    'get_terms_from_graph',
    'from_species',
    'parse_xml_gz',
    'get_converted_obos',
]

logger = logging.getLogger(__name__)
HERE = os.path.abspath(os.path.dirname(__file__))


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


def get_converted_obos() -> Iterable[Obo]:
    """Get all modules in the PyOBO sources."""
    for name in os.listdir(HERE):
        if (
            name in {'__init__.py', '__main__.py', 'cli.py', 'utils.py'}
            or not os.path.isfile(name)
            or not name.endswith('.py')
        ):
            continue
        prefix = name[:-len('.py')]
        module = import_module(prefix)
        yield module.get_obo()
