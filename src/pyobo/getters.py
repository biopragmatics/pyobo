# -*- coding: utf-8 -*-

"""Utilities for OBO files."""

import logging
import os
from typing import Optional
from urllib.request import urlretrieve

import networkx as nx

from .cache_utils import ensure_obo_graph
from .constants import CURATED_URLS
from .path_utils import ensure_path, get_prefix_obo_path
from .registries import get_obofoundry
from .sources import CONVERTED, get_converted_obo

__all__ = [
    'get_obo_graph',
    'get_obo_graph_by_url',
    'get_obo_graph_by_prefix',
]

logger = logging.getLogger(__name__)


class MissingOboBuild(RuntimeError):
    """Raised when OBOFoundry doesn't track an OBO file, but only has OWL."""


def get_obo_graph(prefix: str, *, url: Optional[str] = None) -> nx.MultiDiGraph:
    """Get the OBO file by prefix or URL."""
    if prefix in CONVERTED:
        get_converted_obo(prefix).write_default()
    if url is None:
        return get_obo_graph_by_prefix(prefix)
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
        return ensure_path(prefix, CURATED_URLS[prefix])

    path = get_prefix_obo_path(prefix)
    if os.path.exists(path):
        return path

    obofoundry = get_obofoundry(mappify=True)
    entry = obofoundry.get(prefix)
    if entry is None:
        raise ValueError(f'OBO Foundry is missing the prefix: {prefix}')

    build = entry.get('build')
    if build is None:
        raise MissingOboBuild(f'OBO Foundry is missing a build for: {prefix}')
    url = build['source_url']
    return ensure_path(prefix, url)
