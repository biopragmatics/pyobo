# -*- coding: utf-8 -*-

"""Download information from several registries."""

import logging
from dataclasses import dataclass
from typing import Dict, Mapping, Optional

from .metaregistry import CURATED_REGISTRY_DATABASE, OBSOLETE
from .miriam import get_miriam
from .obofoundry import get_obofoundry
from .ols import get_ols

__all__ = [
    'Resource',
    'get_namespace_synonyms',
    'get_metaregistry',
]

logger = logging.getLogger(__name__)


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

    for key, values in CURATED_REGISTRY_DATABASE.items():
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


def get_metaregistry(try_new=False) -> Mapping[str, Resource]:
    """Get a combine registry."""
    rv: Dict[str, Resource] = {}

    synonym_to_prefix = {}
    for prefix, entry in CURATED_REGISTRY_DATABASE.items():
        if prefix in OBSOLETE:
            continue
        synonym_to_prefix[prefix.lower()] = prefix

        title = entry.get('title')
        if title is not None:
            synonym_to_prefix[title.lower()] = prefix
        for synonym in entry.get("synonyms", {}):
            synonym_to_prefix[synonym.lower()] = prefix

    for entry in get_miriam():
        prefix = entry['prefix']
        if prefix in OBSOLETE:
            continue
        rv[prefix] = Resource(
            name=entry['name'],
            prefix=prefix,
            pattern=entry['pattern'],
            miriam_id=entry['mirId'],
            # namespace_in_pattern=namespace['namespaceEmbeddedInLui'],
        )

    for entry in sorted(get_obofoundry(), key=lambda x: x['id'].lower()):
        prefix = entry['id'].lower()
        is_obsolete = entry.get('is_obsolete') or prefix in OBSOLETE
        already_found = prefix in rv
        if already_found:
            if is_obsolete:
                del rv[prefix]
            else:
                rv[prefix].obofoundry_id = prefix
            continue
        elif is_obsolete:
            continue

        title = entry['title']
        prefix = synonym_to_prefix.get(prefix, prefix)
        curated_info = CURATED_REGISTRY_DATABASE.get(prefix)
        if curated_info and 'pattern' in curated_info:
            # namespace_in_pattern = curated_registry.get('namespace_in_pattern')
            rv[prefix] = Resource(
                name=title,
                prefix=prefix,
                pattern=curated_info['pattern'],
                # namespace_in_pattern=namespace_in_pattern,
            )
            continue

        if not try_new:
            continue

        if not curated_info:
            print(f'missing curated pattern for {prefix}')
            leng = _sample_graph(prefix)
            if leng:
                print(f'"{prefix}": {{\n   "pattern": "\\\\d{{{leng}}}"\n}},')
            continue
        if curated_info.get('not_available_as_obo') or curated_info.get('no_own_terms'):
            continue

    for prefix, entry in CURATED_REGISTRY_DATABASE.items():
        if prefix in rv:
            continue
        name = entry.get('name')
        pattern = entry.get('pattern')
        if not name or not pattern:
            continue
        rv[prefix] = Resource(
            name=name,
            prefix=prefix,
            pattern=pattern,
        )

        # print(f'unhandled {prefix}')
    return rv


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
