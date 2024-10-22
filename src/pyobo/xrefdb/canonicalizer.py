"""Tools for canonicalizing a CURIE based on a priority list."""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Optional

import networkx as nx
import pandas as pd
from more_itertools import pairwise
from tqdm.auto import tqdm

from .priority import DEFAULT_PRIORITY_LIST
from .xrefs_pipeline import get_graph_from_xref_df
from .. import resource_utils
from ..utils.io import get_reader, get_writer

__all__ = [
    "Canonicalizer",
    "all_shortest_paths",
    "single_source_shortest_path",
    "get_equivalent",
    "get_priority_curie",
    "remap_file_stream",
]


@dataclass
class Canonicalizer:
    """Wraps a graph and priority list to allow getting the best identifier."""

    #: A graph from :func:`get_graph_from_xref_df`
    graph: nx.Graph

    #: A list of prefixes. The ones with the lower index are higher priority
    priority: Optional[list[str]] = None

    #: Longest length paths allowed
    cutoff: int = 5

    _priority: Mapping[str, int] = field(init=False)

    def __post_init__(self):
        """Initialize the priority map based on the priority list."""
        if self.priority is None:
            self.priority = DEFAULT_PRIORITY_LIST
        self._priority = {entry: len(self.priority) - i for i, entry in enumerate(self.priority)}

    def _key(self, curie: str) -> Optional[int]:
        prefix = self.graph.nodes[curie]["prefix"]
        return self._priority.get(prefix)

    def _get_priority_dict(self, curie: str) -> Mapping[str, int]:
        return dict(self._iterate_priority_targets(curie))

    def _iterate_priority_targets(self, curie: str) -> Iterable[tuple[str, int]]:
        for target in nx.single_source_shortest_path(self.graph, curie, cutoff=self.cutoff):
            priority = self._key(target)
            if priority is not None:
                yield target, priority
            elif target == curie:
                yield target, 0
            else:
                yield target, -1

    def canonicalize(self, curie: str) -> str:
        """Get the best CURIE from the given CURIE."""
        if curie not in self.graph:
            return curie
        priority_dict = self._get_priority_dict(curie)
        return max(priority_dict, key=priority_dict.get)  # type:ignore

    @classmethod
    def get_default(cls, priority: Optional[Iterable[str]] = None) -> "Canonicalizer":
        """Get the default canonicalizer."""
        if priority is not None:
            priority = tuple(priority)
        return cls._get_default_helper(priority=priority)

    @classmethod
    @lru_cache
    def _get_default_helper(cls, priority: Optional[tuple[str, ...]] = None) -> "Canonicalizer":
        """Help get the default canonicalizer."""
        graph = cls._get_default_graph()
        return cls(graph=graph, priority=list(priority) if priority else None)

    @staticmethod
    @lru_cache
    def _get_default_graph() -> nx.Graph:
        df = resource_utils.ensure_inspector_javert_df()
        graph = get_graph_from_xref_df(df)
        return graph

    def iterate_flat_mapping(self, use_tqdm: bool = True) -> Iterable[tuple[str, str]]:
        """Iterate over the canonical mapping from all nodes to their canonical CURIEs."""
        nodes = self.graph.nodes()
        if use_tqdm:
            nodes = tqdm(
                nodes,
                total=self.graph.number_of_nodes(),
                desc="building flat mapping",
                unit_scale=True,
                unit="CURIE",
            )
        for node in nodes:
            yield node, self.canonicalize(node)

    def get_flat_mapping(self, use_tqdm: bool = True) -> Mapping[str, str]:
        """Get a canonical mapping from all nodes to their canonical CURIEs."""
        return dict(self.iterate_flat_mapping(use_tqdm=use_tqdm))

    def single_source_shortest_path(
        self,
        curie: str,
        cutoff: Optional[int] = None,
    ) -> Optional[Mapping[str, list[Mapping[str, str]]]]:
        """Get all shortest paths between given entity and its equivalent entities."""
        return single_source_shortest_path(graph=self.graph, curie=curie, cutoff=cutoff)

    def all_shortest_paths(
        self, source_curie: str, target_curie: str
    ) -> list[list[Mapping[str, str]]]:
        """Get all shortest paths between the two entities."""
        return all_shortest_paths(
            graph=self.graph, source_curie=source_curie, target_curie=target_curie
        )

    @classmethod
    def from_df(cls, df: pd.DataFrame) -> "Canonicalizer":
        """Instantiate from a dataframe."""
        return cls(graph=get_graph_from_xref_df(df))


def all_shortest_paths(
    graph: nx.Graph, source_curie: str, target_curie: str
) -> list[list[Mapping[str, str]]]:
    """Get all shortest paths between the two CURIEs."""
    _paths = nx.all_shortest_paths(graph, source=source_curie, target=target_curie)
    return [
        [
            {"source": s, "target": t, "provenance": graph[s][t]["source"]}
            for s, t in pairwise(_path)
        ]
        for _path in _paths
    ]


def single_source_shortest_path(
    graph: nx.Graph,
    curie: str,
    cutoff: Optional[int] = None,
) -> Optional[Mapping[str, list[Mapping[str, str]]]]:
    """Get the shortest path from the CURIE to all elements of its equivalence class.

    Things that didn't work:

    Unresponsive
    ------------
    .. code-block:: python

        for curies in tqdm(
            nx.connected_components(graph), desc="filling connected components", unit_scale=True
        ):
            for c1, c2 in itt.combinations(curies, r=2):
                if not graph.has_edge(c1, c2):
                    graph.add_edge(c1, c2, inferred=True)

    Way too slow
    ------------
    .. code-block:: python

        for curie in tqdm(
            graph, total=graph.number_of_nodes(), desc="mapping connected components", unit_scale=True
        ):
            for incident_curie in nx.node_connected_component(graph, curie):
                if not graph.has_edge(curie, incident_curie):
                    graph.add_edge(curie, incident_curie, inferred=True)

    Also consider the condensation of the graph:
    https://networkx.github.io/documentation/stable/reference/algorithms/generated/networkx.algorithms.components.condensation.html#networkx.algorithms.components.condensation
    """
    if curie not in graph:
        return None
    rv = nx.single_source_shortest_path(graph, curie, cutoff=cutoff)
    return {
        k: [
            {"source": s, "target": t, "provenance": graph[s][t]["provenance"]}
            for s, t in pairwise(v)
        ]
        for k, v in rv.items()
        if k != curie  # don't map to self
    }


def get_equivalent(curie: str, cutoff: Optional[int] = None) -> set[str]:
    """Get equivalent CURIEs."""
    canonicalizer = Canonicalizer.get_default()
    r = canonicalizer.single_source_shortest_path(curie=curie, cutoff=cutoff)
    return set(r or [])


def get_priority_curie(curie: str) -> str:
    """Get the priority CURIE mapped to the best namespace."""
    canonicalizer = Canonicalizer.get_default()
    return canonicalizer.canonicalize(curie)


def remap_file_stream(file_in, file_out, column: int, sep="\t") -> None:
    """Remap a file."""
    reader = get_reader(file_in, sep=sep)
    writer = get_writer(file_out, sep=sep)
    for row in reader:
        row[column] = get_priority_curie(row[column])
        writer.writerow(row)
