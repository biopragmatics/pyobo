# -*- coding: utf-8 -*-

"""Utilities for OBO files."""

import logging
import os
from typing import Mapping, Optional
from urllib.parse import urlparse
from urllib.request import urlretrieve

import networkx as nx
import obonet

from pyobo.constants import PYOBO_HOME
from pyobo.registries import get_obofoundry

logger = logging.getLogger(__name__)


class MissingOboBuild(RuntimeError):
    """Raised when OBOFoundry doesn't track an OBO file, but only has OWL."""


def get_prefix_directory(prefix: str) -> str:
    """Get the directory."""
    directory = os.path.abspath(os.path.join(PYOBO_HOME, prefix))
    os.makedirs(directory, exist_ok=True)
    return directory


def ensure_path(prefix: str, url: str, path: Optional[str] = None) -> str:
    """Download a file if it doesn't exist."""
    if path is None:
        parse_result = urlparse(url)
        path = os.path.basename(parse_result.path)

    directory = get_prefix_directory(prefix)
    path = os.path.join(directory, path)

    if not os.path.exists(path):
        logger.info('downloading %s OBO from %s', prefix, url)
        urlretrieve(url, path)

    return path


def get_prefix_obo_path(prefix: str) -> str:
    """Get the canonical path to the OBO file."""
    return os.path.join(get_prefix_directory(prefix), f"{prefix}.obo")


CURATED_URLS = {
    'mp': 'http://purl.obolibrary.org/obo/mp.obo',
}


def ensure_obo_path(prefix: str) -> str:
    """Get the path to the OBO file and download if missing."""
    if prefix in CURATED_URLS:
        return ensure_path(prefix, CURATED_URLS[prefix])

    path = get_prefix_obo_path(prefix)
    if os.path.exists(path):
        return path

    obofoundry = get_obofoundry(mappify=True)
    entry = obofoundry.get(prefix)
    if entry is None:
        raise ValueError(f'Missing prefix: {prefix}')

    build = entry.get('build')
    if build is None:
        raise MissingOboBuild(f'No OBO build for {prefix}')
    url = build['source_url']
    return ensure_path(prefix, url)


def get_obo_graph(prefix: str) -> nx.MultiDiGraph:
    """Get the OBO file as a graph using the OBOFoundry registry URL and cache if not already."""
    path = ensure_obo_path(prefix)

    pickle_path = f'{path}.pickle'
    if os.path.exists(pickle_path):
        logger.debug('loading %s OBO from pickle: %s', prefix, pickle_path)
        return nx.read_gpickle(pickle_path)

    logger.info('parsing %s OBO from %s', prefix, path)
    graph = obonet.read_obo(path)
    nx.write_gpickle(graph, pickle_path)
    return graph


def get_obo_graph_by_url(prefix: str, url: str) -> nx.MultiDiGraph:
    """Get the OBO file as a graph using the given URL and cache if not already."""
    d = get_prefix_directory(prefix)
    path = os.path.join(d, f'{prefix}.obo')
    if not os.path.exists(path):
        logger.info('downloading %s OBO from %s', prefix, url)
        urlretrieve(url, path)

    pickle_path = os.path.join(d, f'{prefix}.obo.pickle')
    if os.path.exists(pickle_path):
        logger.debug('loading %s OBO from pickle: %s', prefix, pickle_path)
        return nx.read_gpickle(pickle_path)

    logger.info('parsing %s OBO from %s', prefix, path)
    graph = obonet.read_obo(path)
    nx.write_gpickle(graph, pickle_path)
    return graph


def get_id_name_mapping(prefix: str, url: Optional[str] = None) -> Mapping[str, str]:
    """Get an identifier to name mapping for the OBO file."""
    path = os.path.join(get_prefix_directory(prefix), f"{prefix}.mapping.tsv")
    if os.path.exists(path):
        logger.debug('loading %s mapping from %s', prefix, path)
        with open(path) as file:
            return dict(line.strip().split('\t') for line in file)

    if url is None:
        graph = get_obo_graph(prefix)
    else:
        graph = get_obo_graph_by_url(prefix, url)

    rv = {}
    logger.info('writing %s mapping to %s', prefix, path)
    with open(path, 'w') as file:
        for node, data in graph.nodes(data=True):
            name = data.get('name')
            if name is None:
                continue

            rv[node] = name
            print(node, name, sep='\t', file=file)

    return rv
