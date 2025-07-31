"""Utilities for caching files."""

import json
import logging
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Generic, TypeVar

import networkx as nx
from pystow.cache import Cached
from pystow.cache import CachedCollection as cached_collection  # noqa:N813
from pystow.cache import CachedDataFrame as cached_df  # noqa:N813
from pystow.cache import CachedJSON as cached_json  # noqa:N813
from pystow.cache import CachedPickle as cached_pickle  # noqa:N813

from .io import open_map_tsv, open_multimap_tsv, safe_open, write_map_tsv, write_multimap_tsv

__all__ = [
    "cached_collection",
    "cached_df",
    # implemented here
    "cached_graph",
    # from pystow
    "cached_json",
    "cached_mapping",
    "cached_multidict",
    "cached_pickle",
]

logger = logging.getLogger(__name__)

X = TypeVar("X")


class _CachedMapping(Cached[X], Generic[X]):
    """A cache for simple mappings."""

    def __init__(
        self,
        path: str | Path,
        header: Iterable[str],
        *,
        use_tqdm: bool = False,
        force: bool = False,
        cache: bool = True,
    ):
        """Initialize the mapping cache."""
        super().__init__(path=path, cache=cache, force=force)
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

NODE_LINK_STYLE = "links"  # TODO update to "edges"


def get_gzipped_graph(path: str | Path) -> nx.MultiDiGraph:
    """Read a graph that's gzipped nodelink."""
    with safe_open(path, read=True) as file:
        return nx.node_link_graph(json.load(file), edges=NODE_LINK_STYLE)


def write_gzipped_graph(graph: nx.MultiDiGraph, path: str | Path) -> None:
    """Write a graph as gzipped nodelink."""
    with safe_open(path, read=False) as file:
        json.dump(nx.node_link_data(graph, edges=NODE_LINK_STYLE), file)


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
