# -*- coding: utf-8 -*-

"""Download information from several registries."""

import json
import logging
import os
import tempfile
from typing import Mapping, Optional
from urllib.request import urlretrieve

import requests
import yaml

__all__ = [
    'get_obofoundry',
    'get_miriam',
    'get_ols',
    'get_curated_registry',
    'get_namespace_synonyms',
    'get_metaregistry',
]

logger = logging.getLogger(__name__)

HERE = os.path.abspath(os.path.dirname(__file__))

OBOFOUNDRY_URL = 'https://raw.githubusercontent.com/OBOFoundry/OBOFoundry.github.io/master/registry/ontologies.yml'
MIRIAM_URL = 'https://registry.api.identifiers.org/restApi/namespaces'
OLS_URL = 'http://www.ebi.ac.uk/ols/api/ontologies'

OBOFOUNDRY_CACHE_PATH = os.path.join(HERE, 'obofoundry.json')
MIRIAM_CACHE_PATH = os.path.join(HERE, 'miriam.json')
OLS_CACHE_PATH = os.path.join(HERE, 'ols.json')

#: The self-curated registry metadatabase
CURATED_REGISTRY_PATH = os.path.join(HERE, 'metaregistry.json')


def get_obofoundry(cache_path: Optional[str] = OBOFOUNDRY_CACHE_PATH, mappify: bool = False):
    """Get the OBO Foundry registry."""
    if cache_path is not None and os.path.exists(cache_path):
        with open(cache_path) as file:
            rv = json.load(file)
            if mappify:
                return _mappify(rv, 'id')
            return rv

    with tempfile.TemporaryDirectory() as d:
        yaml_path = os.path.join(d, 'obofoundry.yml')
        urlretrieve(OBOFOUNDRY_URL, yaml_path)
        with open(yaml_path) as file:
            rv = yaml.full_load(file)

    rv = rv['ontologies']
    for s in rv:
        for k in ('browsers', 'usages', 'depicted_by', 'products'):
            if k in s:
                del s[k]

    if cache_path is not None:
        with open(cache_path, 'w') as file:
            json.dump(rv, file, indent=2)

    if mappify:
        rv = _mappify(rv, 'id')

    return rv


def _mappify(j, k):
    return {entry[k]: entry for entry in j}


def get_miriam(cache_path: Optional[str] = MIRIAM_CACHE_PATH, mappify: bool = False):
    """Get the MIRIAM registry."""
    return _ensure(MIRIAM_URL, embedded_key='namespaces', cache_path=cache_path, mappify_key=mappify and 'prefix')


def get_ols(cache_path: Optional[str] = OLS_CACHE_PATH, mappify: bool = False):
    """Get the OLS registry."""
    return _ensure(OLS_URL, embedded_key='ontologies', cache_path=cache_path, mappify_key=mappify and 'ontologyId')


def _ensure(url, embedded_key, cache_path: Optional[str] = None, mappify_key: Optional[str] = None):
    if cache_path is not None and os.path.exists(cache_path):
        with open(cache_path) as file:
            return json.load(file)

    rv = _download_paginated(url, embedded_key=embedded_key)
    if cache_path is not None:
        with open(cache_path, 'w') as file:
            json.dump(rv, file, indent=2)

    if mappify_key is not None:
        rv = _mappify(rv, mappify_key)

    return rv


def _download_paginated(start_url, embedded_key):
    results = []
    url = start_url
    while True:
        logger.debug('getting', url)
        g = requests.get(url)
        j = g.json()
        r = j['_embedded'][embedded_key]
        results.extend(r)
        links = j['_links']
        if 'next' not in links:
            break
        url = links['next']['href']
    return results


def get_curated_registry():
    """Get the metaregistry."""
    with open(CURATED_REGISTRY_PATH) as file:
        x = json.load(file)
    with open(CURATED_REGISTRY_PATH, 'w') as file:
        json.dump(x, file, indent=2, sort_keys=True)
    return x


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

    metaregistry = get_curated_registry()
    for key, values in metaregistry['database'].items():
        _add_variety(key, key)
        for synonym in values.get('synonyms', []):
            _add_variety(synonym, key)

    return synonym_to_key


def get_metaregistry(try_new=False) -> Mapping[str, Mapping[str, str]]:
    """Get a combine registry."""
    x = get_curated_registry()

    obsolete_registry = x['obsolete']
    curated_registry = x['database']
    synonym_to_prefix = {}
    for prefix, entry in curated_registry.items():
        if prefix in obsolete_registry:
            continue
        synonym_to_prefix[prefix.lower()] = prefix

        if 'title' in entry:
            synonym_to_prefix[entry['title'].lower()] = prefix
        for synonym in entry.get("synonyms", {}):
            synonym_to_prefix[synonym.lower()] = prefix

    rv = {}
    for namespace in get_miriam():
        prefix = namespace['prefix']
        if prefix in obsolete_registry:
            continue
        rv[prefix] = dict(
            prefix=prefix,
            name=namespace['name'],
            pattern=namespace['pattern'],
            # namespace_in_pattern=namespace['namespaceEmbeddedInLui'],
        )

    for namespace in sorted(get_obofoundry(), key=lambda x: x['id'].lower()):
        prefix = namespace['id'].lower()
        is_obsolete = namespace.get('is_obsolete') or prefix in obsolete_registry
        already_found = prefix in rv

        if is_obsolete or already_found:
            if is_obsolete and already_found:
                del rv[prefix]
            continue

        title = namespace['title']
        prefix = synonym_to_prefix.get(prefix, prefix)
        curated_info = curated_registry.get(prefix)
        if curated_info and 'pattern' in curated_info:
            # namespace_in_pattern = curated_registry.get('namespace_in_pattern')
            rv[prefix] = dict(
                prefix=prefix,
                name=title,
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


if __name__ == '__main__':
    r = get_metaregistry()
