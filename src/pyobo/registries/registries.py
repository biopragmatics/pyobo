# -*- coding: utf-8 -*-

"""Download information from several registries."""

from dataclasses import dataclass
from typing import Optional
from urllib.error import HTTPError

from obonet import read_obo

__all__ = [
    'Resource',
]


@dataclass
class Resource:
    """A class for holding resource information."""

    name: str
    prefix: str
    pattern: str
    miriam_id: Optional[str] = None
    obofoundry_id: Optional[str] = None
    ols_id: Optional[str] = None


def _sample_graph(prefix: str):
    url = f'http://purl.obolibrary.org/obo/{prefix}.obo'
    try:
        graph = read_obo(url)
    except HTTPError:
        print(f'{prefix} URL invalid {url}. See: http://www.obofoundry.org/ontology/{prefix}')
        return False
    except ValueError:
        print(f'Issue parsing {url}. See: http://www.obofoundry.org/ontology/{prefix}')
        return False

    nodes = (
        node
        for node in graph
        if node.lower().startswith(prefix)
    )
    nodes = [
        node
        for node, _ in zip(nodes, range(10))
    ]
    if not nodes:
        print(f'No own terms in {prefix}')
    for node in nodes:
        print('  example', node)

    if all(len(nodes[0]) == len(node) for node in nodes[1:]):
        return len(nodes[0]) - 1 - len(prefix)
