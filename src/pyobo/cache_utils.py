# -*- coding: utf-8 -*-

"""Utilities for caching files."""

import functools
import json
import logging
import os
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Union

import networkx as nx
import obonet

from .io_utils import open_map_tsv, write_map_tsv

logger = logging.getLogger(__name__)

JSONType = Union[
    Dict[str, Any],
    List[Any],
]

MappingGetter = Callable[[], Mapping[str, str]]
JSONGetter = Callable[[], JSONType]
GraphGetter = Callable[[], nx.MultiDiGraph]


def cached_mapping(path: str, header: Iterable[str]) -> Callable[[MappingGetter], MappingGetter]:  # noqa: D202
    """Create a decorator to apply to a mapping getter."""

    def wrapped(f: MappingGetter) -> MappingGetter:  # noqa: D202
        """Wrap a mapping getter so it can be auto-loaded from a cache."""

        @functools.wraps(f)
        def _wrapped() -> Mapping[str, str]:
            if os.path.exists(path):
                return open_map_tsv(path)
            rv = f()
            write_map_tsv(path=path, header=header, rv=rv)
            return rv

        return _wrapped

    return wrapped


def cached_json(path: str) -> Callable[[JSONGetter], JSONGetter]:  # noqa: D202
    """Create a decorator to apply to a mapping getter."""

    def wrapped(f: JSONGetter) -> JSONGetter:  # noqa: D202
        """Wrap a mapping getter so it can be auto-loaded from a cache."""

        @functools.wraps(f)
        def _wrapped() -> JSONType:
            if os.path.exists(path):
                with open(path) as file:
                    return json.load(file)
            rv = f()
            with open(path, 'w') as file:
                json.dump(rv, file, indent=2)
            return rv

        return _wrapped

    return wrapped


def cached_graph(path: str) -> Callable[[GraphGetter], GraphGetter]:  # noqa: D202
    """Create a decorator to apply to a graph getter."""

    def wrapped(f: GraphGetter) -> GraphGetter:  # noqa: D202
        """Wrap a mapping getter so it can be auto-loaded from a cache."""

        @functools.wraps(f)
        def _wrapped() -> nx.MultiDiGraph:
            if os.path.exists(path):
                logger.debug('loading graph from pickle: %s', path)
                return nx.read_gpickle(path)
            rv = f()
            nx.write_gpickle(rv, path)
            return rv

        return _wrapped

    return wrapped


def ensure_obo_graph(path: str, pickle_path: Optional[str] = None) -> nx.MultiDiGraph:
    """Get an OBO graph from a given path."""
    if pickle_path is None:
        pickle_path = f'{path}.pickle'

    @cached_graph(path=pickle_path)
    def _read_obo() -> nx.MultiDiGraph:
        return obonet.read_obo(path)

    return _read_obo()
