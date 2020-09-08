# -*- coding: utf-8 -*-

"""Download information from several registries."""

import logging
from dataclasses import dataclass
from functools import lru_cache
from typing import Mapping, Optional

from .metaregistry import get_curated_registry_database
from .miriam import get_miriam
from .ols import get_ols

__all__ = [
    'Resource',
    'get_namespace_synonyms',
]

logger = logging.getLogger(__name__)


@lru_cache()
def get_namespace_synonyms() -> Mapping[str, str]:
    """Return a mapping from several variants of each synonym to the canonical namespace."""
    synonym_to_key = {}

    def _add_variety(_synonym, _target) -> None:
        synonym_to_key[_synonym] = _target
        synonym_to_key[_synonym.lower()] = _target
        synonym_to_key[_synonym.upper()] = _target
        synonym_to_key[_synonym.casefold()] = _target
        for x, y in [('_', ' '), (' ', '_'), (' ', '')]:
            synonym_to_key[_synonym.replace(x, y)] = _target
            synonym_to_key[_synonym.lower().replace(x, y)] = _target
            synonym_to_key[_synonym.upper().replace(x, y)] = _target
            synonym_to_key[_synonym.casefold().replace(x, y)] = _target

    for entry in get_miriam():
        prefix, name = entry['prefix'], entry['name']
        _add_variety(prefix, prefix)
        _add_variety(name, prefix)

    for entry in get_ols():
        ontology_id = entry['ontologyId']
        _add_variety(ontology_id, ontology_id)
        _add_variety(entry['config']['title'], ontology_id)
        _add_variety(entry['config']['namespace'], ontology_id)

    for key, values in get_curated_registry_database().items():
        _add_variety(key, key)
        for synonym in values.get('synonyms', []):
            _add_variety(synonym, key)

    return synonym_to_key


@dataclass
class Resource:
    """A class for holding resource information."""

    name: str
    prefix: str
    pattern: str
    miriam_id: Optional[str] = None
    obofoundry_id: Optional[str] = None
    ols_id: Optional[str] = None


def _sample_graph(prefix):
    from obonet import read_obo
    from urllib.error import HTTPError
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
