"""Utilities for caching files."""

import gzip
import json
import logging
import os
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Generic, TypeVar, Union

import networkx as nx
from pystow.cache import Cached
from pystow.cache import CachedCollection as cached_collection  # noqa:N813
from pystow.cache import CachedDataFrame as cached_df  # noqa:N813
from pystow.cache import CachedJSON as cached_json  # noqa:N813
from pystow.cache import CachedPickle as cached_pickle  # noqa:N813

from .io import open_map_tsv, open_multimap_tsv, write_map_tsv, write_multimap_tsv

__all__ = [
    # from pystow
    "cached_json",
    "cached_collection",
    "cached_df",
    "cached_pickle",
    # implemented here
    "cached_graph",
    "cached_mapping",
    "cached_multidict",
]

logger = logging.getLogger(__name__)

X = TypeVar("X")


class _CachedMapping(Cached[X], Generic[X]):
    """A cache for simple mappings."""

    def __init__(
        self,
        path: Union[str, Path, os.PathLike],
        header: Iterable[str],
        *,
        use_tqdm: bool = False,
        force: bool = False,
    ):
        """Initialize the mapping cache."""
        super().__init__(path=path, force=force)
        self.header = header
        self.use_tqdm = use_tqdm


class CachedMapping(_CachedMapping[Mapping[str, str]]):
    """A cache for simple mappings."""

    def load(self) -> Mapping[str, str]:
        """Load a TSV file."""
        return open_map_tsv(self.path, use_tqdm=self.use_tqdm)

    def dump(self, rv: Mapping[str, str]) -> None:
        """Write a TSV file."""
        write_map_tsv(path=self.path, header=self.header, rv=rv)


cached_mapping = CachedMapping


def get_gzipped_graph(path: Union[str, Path]) -> nx.MultiDiGraph:
    """Read a graph that's gzipped nodelink."""
    with gzip.open(path, "rt") as file:
        return nx.node_link_graph(json.load(file))


def write_gzipped_graph(graph: nx.MultiDiGraph, path: Union[str, Path]) -> None:
    """Write a graph as gzipped nodelink."""
    with gzip.open(path, "wt") as file:
        json.dump(nx.node_link_data(graph), file)


class CachedGraph(Cached[nx.MultiDiGraph]):
    """A cache for multidigraphs."""

    def load(self) -> nx.MultiDiGraph:
        """Load a graph file."""
        return get_gzipped_graph(self.path)

    def dump(self, rv: nx.MultiDiGraph) -> None:
        """Write a graph file."""
        write_gzipped_graph(rv, self.path)


cached_graph = CachedGraph


class CachedMultidict(_CachedMapping[Mapping[str, list[str]]]):
    """A cache for complex mappings."""

    def load(self) -> Mapping[str, list[str]]:
        """Load a TSV file representing a multimap."""
        return open_multimap_tsv(self.path, use_tqdm=self.use_tqdm)

    def dump(self, rv: Mapping[str, list[str]]) -> None:
        """Write a TSV file representing a multimap."""
        write_multimap_tsv(path=self.path, header=self.header, rv=rv)


cached_multidict = CachedMultidict
