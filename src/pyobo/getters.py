# -*- coding: utf-8 -*-

"""Utilities for OBO files."""

import logging
import os
from typing import Optional
from urllib.request import urlretrieve

import networkx as nx
import obonet

from .cache_utils import cached_graph
from .constants import CURATED_URLS
from .path_utils import ensure_path, get_prefix_obo_path
from .registries import get_obofoundry
from .sources import CONVERTED, get_converted_obo
from .struct import Obo

__all__ = [
    'get',
]

logger = logging.getLogger(__name__)


class MissingOboBuild(RuntimeError):
    """Raised when OBOFoundry doesn't track an OBO file, but only has OWL."""


def get(prefix: str, *, url: Optional[str] = None, local: bool = False) -> Obo:
    """Get the OBO for a given graph."""
    graph = get_obo_graph(prefix=prefix, url=url, local=local)
    return Obo.from_obonet(graph)


def get_obo_graph(prefix: str, *, url: Optional[str] = None, local: bool = False) -> nx.MultiDiGraph:
    """Get the OBO file by prefix or URL."""
    if prefix in CONVERTED:
        obo = get_converted_obo(prefix)
        obo.write_default()
    if url is None:
        return get_obo_graph_by_prefix(prefix)
    elif local:
        return obonet.read_obo(url)
    else:
        return get_obo_graph_by_url(prefix, url)


def get_obo_graph_by_url(prefix: str, url: str) -> nx.MultiDiGraph:
    """Get the OBO file as a graph using the given URL and cache if not already."""
    path = get_prefix_obo_path(prefix)
    if not os.path.exists(path):
        logger.info('downloading %s OBO from %s', prefix, url)
        urlretrieve(url, path)
    return ensure_obo_graph(path)


def get_obo_graph_by_prefix(prefix: str) -> nx.MultiDiGraph:
    """Get the OBO file as a graph using the OBOFoundry registry URL and cache if not already."""
    path = ensure_obo_path(prefix)
    return ensure_obo_graph(path=path)


def ensure_obo_path(prefix: str) -> str:
    """Get the path to the OBO file and download if missing."""
    if prefix in CURATED_URLS:
        curated_url = CURATED_URLS[prefix]
        logger.debug(f'loading {prefix} OBO from curated URL: {curated_url}')
        return ensure_path(prefix, url=curated_url)

    path = get_prefix_obo_path(prefix)
    if os.path.exists(path):
        logger.debug(f'{prefix} OBO already exists at {path}')
        return path

    obofoundry = get_obofoundry(mappify=True)
    entry = obofoundry.get(prefix)
    if entry is None:
        raise ValueError(f'OBO Foundry is missing the prefix: {prefix}')

    build = entry.get('build')
    if build is None:
        raise MissingOboBuild(f'OBO Foundry is missing a build for: {prefix}')

    url = build.get('source_url')
    if url is None:
        raise MissingOboBuild(f'OBO Foundry build is missing a URL for: {prefix}, {build}')

    return ensure_path(prefix, url)


def ensure_obo_graph(path: str) -> nx.MultiDiGraph:
    """Get an OBO graph from a given path."""
    cache_path = f'{path}.json.gz'

    @cached_graph(path=cache_path)
    def _read_obo() -> nx.MultiDiGraph:
        return obonet.read_obo(path)

    return _read_obo()
