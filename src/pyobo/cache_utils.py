# -*- coding: utf-8 -*-

"""Utilities for caching files."""

import functools
import gzip
import json
import logging
import os
from typing import Any, Callable, Dict, Iterable, List, Mapping, Union

import networkx as nx
import pandas as pd

from .io_utils import open_map_tsv, open_multimap_tsv, write_map_tsv, write_multimap_tsv

logger = logging.getLogger(__name__)

JSONType = Union[
    Dict[str, Any],
    List[Any],
]

MappingGetter = Callable[[], Mapping[str, str]]
MultiMappingGetter = Callable[[], Mapping[str, List[str]]]
JSONGetter = Callable[[], JSONType]
GraphGetter = Callable[[], nx.MultiDiGraph]
DataFrameGetter = Callable[[], pd.DataFrame]


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
                logger.debug('loading pre-compiled graph from: %s', path)
                with gzip.open(path, 'rt') as file:
                    return nx.node_link_graph(json.load(file))
            graph = f()
            with gzip.open(path, 'wt') as file:
                json.dump(nx.node_link_data(graph), file)
            return graph

        return _wrapped

    return wrapped


def cached_df(path: str, sep: str = '\t', **kwargs):  # noqa: D202
    """Create a decorator to apply to a dataframe getter."""

    def wrapped(f: DataFrameGetter) -> DataFrameGetter:  # noqa: D202
        """Wrap a mapping getter so it can be auto-loaded from a cache."""

        @functools.wraps(f)
        def _wrapped() -> pd.DataFrame:
            if os.path.exists(path):
                return pd.read_csv(path, sep=sep, **kwargs)
            rv = f()
            rv.to_csv(path, sep=sep, index=False)
            return rv

        return _wrapped

    return wrapped


def cached_multidict(path: str, header: Iterable[str]):  # noqa: D202
    """Create a decorator to apply to a dataframe getter."""

    def wrapped(f: MultiMappingGetter) -> MultiMappingGetter:  # noqa: D202
        """Wrap a mapping getter so it can be auto-loaded from a cache."""

        @functools.wraps(f)
        def _wrapped() -> Mapping[str, List[str]]:
            if os.path.exists(path):
                return open_multimap_tsv(path)
            rv = f()
            write_multimap_tsv(path=path, header=header, rv=rv)
            return rv

        return _wrapped

    return wrapped
