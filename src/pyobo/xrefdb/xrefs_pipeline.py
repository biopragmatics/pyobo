# -*- coding: utf-8 -*-

"""Pipeline for extracting all xrefs from OBO documents available."""

import itertools as itt
import os
import urllib.error
from dataclasses import dataclass, field
from typing import Iterable, List, Mapping, Optional

import click
import networkx as nx
import pandas as pd
from more_itertools import pairwise
from tqdm import tqdm

from .sources import iter_sourced_xref_dfs
from ..extract import get_xrefs_df
from ..getters import MissingOboBuild
from ..path_utils import get_prefix_directory
from ..registries import get_metaregistry

SKIP = {
    'obi',
    'ncbigene',  # too big, refs acquired from other dbs
    'pubchem.compound',  # to big, can't deal with this now
}
COLUMNS = ['source_ns', 'source_id', 'target_ns', 'target_id', 'source']


@dataclass
class Canonicalizer:
    """Wraps a graph and priority list to allow getting the best identifier."""

    #: A graph from :func:`get_graph_from_xref_df`
    graph: nx.Graph
    #: A list of prefixes. The ones with the lower index are higher priority
    priority: List[str]

    _priority: Mapping[str, int] = field(init=False)

    def __post_init__(self):
        """Initialize the priority map based on the priority list."""
        self._priority = {
            entry: len(self.priority) - i
            for i, entry in enumerate(self.priority)
        }

    def _key(self, curie: str) -> Optional[int]:
        prefix = self.graph.nodes[curie]['prefix']
        return self._priority.get(prefix)

    def _get_priority_dict(self, curie: str) -> Mapping[str, int]:
        rv = {}
        for target in nx.node_connected_component(self.graph, curie):
            priority = self._key(target)
            if priority is not None:
                rv[target] = priority
            elif target == curie:
                rv[target] = 0
            else:
                rv[target] = -1
        return rv

    def canonicalize(self, curie: str) -> str:
        """Get the best CURIE from the given CURIE."""
        if curie not in self.graph:
            return curie
        priority_dict = self._get_priority_dict(curie)
        return max(priority_dict, key=priority_dict.get)


def get_graph_from_xref_df(df: pd.DataFrame) -> nx.Graph:
    """Generate a graph from the mappings dataframe."""
    rv = nx.Graph()

    it = itt.chain(
        df[['source_ns', 'source_id']].drop_duplicates().values,
        df[['target_ns', 'target_id']].drop_duplicates().values,
    )
    it = tqdm(it, desc='loading curies', unit_scale=True)
    for prefix, identifier in it:
        rv.add_node(_to_curie(prefix, identifier), prefix=prefix, identifier=identifier)

    it = tqdm(df.values, total=len(df.index), desc='loading xrefs', unit_scale=True)
    for source_ns, source_id, target_ns, target_id, source in it:
        rv.add_edge(
            _to_curie(source_ns, source_id),
            _to_curie(target_ns, target_id),
            source=source,
        )

    return rv


def _to_curie(prefix: str, identifier: str) -> str:
    return f'{prefix}:{identifier}'


def all_shortest_paths(graph: nx.Graph, source_curie: str, target_curie: str) -> List[List[Mapping[str, str]]]:
    """Get all shortest paths between the two CURIEs."""
    _paths = nx.all_shortest_paths(graph, source=source_curie, target=target_curie)
    return [
        [
            dict(source=s, target=t, provenance=graph[s][t]['source'])
            for s, t in pairwise(_path)
        ]
        for _path in _paths
    ]


def single_source_shortest_path(graph: nx.Graph, curie: str) -> Optional[Mapping[str, List[Mapping[str, str]]]]:
    """Get the shortest path from the CURIE to all elements of its equivalence class.

    Things that didn't work:

    Unresponsive
    ------------
    .. code-block:: python

        for curies in tqdm(nx.connected_components(graph), desc='filling connected components', unit_scale=True):
            for c1, c2 in itt.combinations(curies, r=2):
                if not graph.has_edge(c1, c2):
                    graph.add_edge(c1, c2, inferred=True)

    Way too slow
    ------------
    .. code-block:: python

        for curie in tqdm(graph, total=graph.number_of_nodes(), desc='mapping connected components', unit_scale=True):
            for incident_curie in nx.node_connected_component(graph, curie):
                if not graph.has_edge(curie, incident_curie):
                    graph.add_edge(curie, incident_curie, inferred=True)

    Also consider the condensation of the graph:
    https://networkx.github.io/documentation/stable/reference/algorithms/generated/networkx.algorithms.components.condensation.html#networkx.algorithms.components.condensation
    """
    if curie not in graph:
        return None
    rv = nx.single_source_shortest_path(graph, curie)
    return {
        k: [
            dict(source=s, target=t, provenance=graph[s][t]['source'])
            for s, t in pairwise(v)
        ]
        for k, v in rv.items()
        if k != curie  # don't map to self
    }


def get_xref_df() -> pd.DataFrame:
    """Get the ultimate xref databse."""
    df = pd.concat(_iterate_xref_dfs())
    df.dropna(inplace=True)
    df.sort_values(COLUMNS, inplace=True)
    return df


def _iterate_xref_dfs() -> Iterable[pd.DataFrame]:
    for prefix, _entry in _iterate_metaregistry():
        try:
            df = get_xrefs_df(prefix)
        except MissingOboBuild as e:
            click.secho(f'💾 {prefix}', bold=True)
            click.secho(str(e), fg='yellow')
            url = f'http://purl.obolibrary.org/obo/{prefix}.obo'
            click.secho(f'trying to query purl at {url}', fg='yellow')
            try:
                df = get_xrefs_df(prefix, url=url)
                click.secho(f'resolved {prefix} with {url}', fg='green')
            except Exception as e2:
                click.secho(str(e2), fg='yellow')
                continue
        except (urllib.error.HTTPError, urllib.error.URLError) as e:
            click.secho(f'💾 {prefix}', bold=True)
            click.secho(f'Bad URL for {prefix}')
            click.secho(str(e))
            continue
        except ValueError:
            # click.secho(f'Not in available as OBO through OBO Foundry or PyOBO: {prefix}', fg='yellow')
            continue

        df['source'] = prefix
        df.drop_duplicates(inplace=True)
        yield df

        prefix_directory = get_prefix_directory(prefix)
        if not os.listdir(prefix_directory):
            os.rmdir(prefix_directory)

    yield from iter_sourced_xref_dfs()


def _iterate_metaregistry():
    for prefix, _entry in sorted(get_metaregistry().items()):
        if prefix not in SKIP:
            yield prefix, _entry
