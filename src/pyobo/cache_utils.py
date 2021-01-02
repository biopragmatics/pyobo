# -*- coding: utf-8 -*-

"""Utilities for caching files."""

import functools
import gzip
import json
import logging
import os
import pickle
from pathlib import Path
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


def cached_mapping(
    path: Union[str, Path],
    header: Iterable[str],
    *,
    use_tqdm: bool = False,
    force: bool = False,
) -> Callable[[MappingGetter], MappingGetter]:  # noqa: D202
    """Create a decorator to apply to a mapping getter."""

    def wrapped(f: MappingGetter) -> MappingGetter:  # noqa: D202
        """Wrap a mapping getter so it can be auto-loaded from a cache."""

        @functools.wraps(f)
        def _wrapped() -> Mapping[str, str]:
            if os.path.exists(path) and not force:
                logger.debug('loading from cache at %s', path)
                return open_map_tsv(path, use_tqdm=use_tqdm)
            logger.debug('no cache found at %s', path)
            rv = f()
            logger.debug('writing cache to %s', path)
            write_map_tsv(path=path, header=header, rv=rv)
            return rv

        return _wrapped

    return wrapped


def cached_json(path: Union[str, Path], force: bool = False) -> Callable[[JSONGetter], JSONGetter]:  # noqa: D202
    """Create a decorator to apply to a mapping getter."""

    def wrapped(f: JSONGetter) -> JSONGetter:  # noqa: D202
        """Wrap a mapping getter so it can be auto-loaded from a cache."""

        @functools.wraps(f)
        def _wrapped() -> JSONType:
            if os.path.exists(path) and not force:
                with open(path) as file:
                    return json.load(file)
            rv = f()
            with open(path, 'w') as file:
                json.dump(rv, file, indent=2)
            return rv

        return _wrapped

    return wrapped


def cached_pickle(path: Union[str, Path], force: bool = False):
    """Create a decorator to apply to a pickle getter."""

    def wrapped(f):  # noqa: D202
        """Wrap a mapping getter so it can be auto-loaded from a cache."""

        @functools.wraps(f)
        def _wrapped():
            if os.path.exists(path) and not force:
                with open(path, 'rb') as file:
                    return pickle.load(file)
            rv = f()
            with open(path, 'wb') as file:
                pickle.dump(rv, file, protocol=pickle.HIGHEST_PROTOCOL)
            return rv

        return _wrapped

    return wrapped


def get_gzipped_graph(path: Union[str, Path]) -> nx.MultiDiGraph:
    """Read a graph that's gzipped nodelink."""
    with gzip.open(path, 'rt') as file:
        return nx.node_link_graph(json.load(file))


def write_gzipped_graph(graph: nx.MultiDiGraph, path: Union[str, Path]) -> None:
    """Write a graph as gzipped nodelink."""
    with gzip.open(path, 'wt') as file:
        json.dump(nx.node_link_data(graph), file)


def cached_graph(path: Union[str, Path], force: bool = False) -> Callable[[GraphGetter], GraphGetter]:  # noqa: D202
    """Create a decorator to apply to a graph getter."""

    def wrapped(f: GraphGetter) -> GraphGetter:  # noqa: D202
        """Wrap a mapping getter so it can be auto-loaded from a cache."""

        @functools.wraps(f)
        def _wrapped() -> nx.MultiDiGraph:
            if os.path.exists(path) and not force:
                logger.debug('loading pre-compiled graph from: %s', path)
                return get_gzipped_graph(path)
            graph = f()
            write_gzipped_graph(graph, path)
            return graph

        return _wrapped

    return wrapped


def cached_df(path: Union[str, Path], sep: str = '\t', force: bool = False, **kwargs):  # noqa: D202
    """Create a decorator to apply to a dataframe getter."""

    def wrapped(f: DataFrameGetter) -> DataFrameGetter:  # noqa: D202
        """Wrap a mapping getter so it can be auto-loaded from a cache."""

        @functools.wraps(f)
        def _wrapped() -> pd.DataFrame:
            if os.path.exists(path) and not force:
                logger.info('loading cached dataframe from %s', path)
                return pd.read_csv(
                    path,
                    sep=sep,
                    keep_default_na=False,  # sometimes NA is actually a value
                    **kwargs,
                )
            rv = f()
            rv.to_csv(path, sep=sep, index=False)
            return rv

        return _wrapped

    return wrapped


def cached_multidict(
    path: Union[str, Path],
    header: Iterable[str],
    *,
    use_tqdm: bool = False,
    force: bool = False,
):  # noqa: D202
    """Create a decorator to apply to a dataframe getter."""

    def wrapped(f: MultiMappingGetter) -> MultiMappingGetter:  # noqa: D202
        """Wrap a mapping getter so it can be auto-loaded from a cache."""

        @functools.wraps(f)
        def _wrapped() -> Mapping[str, List[str]]:
            if os.path.exists(path) and not force:
                return open_multimap_tsv(path, use_tqdm=use_tqdm)
            rv = f()
            write_multimap_tsv(path=path, header=header, rv=rv)
            return rv

        return _wrapped

    return wrapped
