# -*- coding: utf-8 -*-

"""Pipeline for extracting all xrefs from OBO documents available."""

import gzip
import itertools as itt
import logging
import os
from dataclasses import dataclass, field
from typing import Iterable, List, Mapping, Optional, Tuple

import networkx as nx
import pandas as pd
from more_itertools import pairwise
from tqdm import tqdm

from .sources import iter_sourced_xref_dfs
from ..extract import get_id_name_mapping, get_xrefs_df
from ..getters import MissingOboBuild, NoOboFoundry
from ..identifier_utils import normalize_prefix
from ..path_utils import ensure_path, get_prefix_directory
from ..registries import get_metaregistry
from ..sources import ncbigene

logger = logging.getLogger(__name__)

SKIP = {
    'obi',
    'ncbigene',  # too big, refs acquired from other dbs
    'pubchem.compound',  # to big, can't deal with this now
    'rnao',  # just really malformed, way too much unconverted OWL
}
SKIP_XREFS = {
    'apo', 'rxno', 'omit', 'mop', 'mamo', 'ido', 'iao', 'gaz', 'fypo', 'nbo',
}
COLUMNS = ['source_ns', 'source_id', 'target_ns', 'target_id', 'source']

DEFAULT_PRIORITY_LIST = [
    # Genes
    'hgnc',
    'rgd',
    'mgi',
    'ncbigene',
    'ensembl',
    'uniprot',
    # protein families and complexes (and famplexes :))
    'complexportal',
    'fplx',
    'ec-code',
    'interpro',
    'pfam',
    'signor',
    # Pathologies/phenotypes
    'efo',
    'doid',
    'hp',
    # Taxa
    'ncbitaxon',
    'itis',
    # If you can get away from MeSH, do it
    'mesh',
]
DEFAULT_PRIORITY_LIST = [normalize_prefix(x) for x in DEFAULT_PRIORITY_LIST]


# TODO a normal graph can easily be turned into a directed graph where each
#  edge points from low priority to higher priority, then the graph can
#  be reduced to a set of star graphs and ultimately to a single dictionary

@dataclass
class Canonicalizer:
    """Wraps a graph and priority list to allow getting the best identifier."""

    #: A graph from :func:`get_graph_from_xref_df`
    graph: nx.Graph
    #: A list of prefixes. The ones with the lower index are higher priority
    priority: List[str] = field(default_factory=lambda: DEFAULT_PRIORITY_LIST)

    #: Longest length paths allowed
    cutoff: int = 5

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
        for target in nx.single_source_shortest_path(self.graph, curie, cutoff=self.cutoff):
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


def summarize_xref_df(df: pd.DataFrame) -> pd.DataFrame:
    """Get all meta-mappings."""
    c = ['source_ns', 'target_ns']
    rv = df[c].groupby(c).size().reset_index()
    rv.columns = ['source_ns', 'target_ns', 'count']
    rv.sort_values('count', inplace=True, ascending=False)
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
    """Get the ultimate xref database."""
    df = pd.concat(_iterate_xref_dfs())
    df.drop_duplicates(inplace=True)
    df.dropna(inplace=True)
    df.sort_values(COLUMNS, inplace=True)
    return df


def _iterate_xref_dfs() -> Iterable[pd.DataFrame]:
    for prefix, _entry in _iterate_metaregistry():
        if prefix in SKIP_XREFS:
            continue
        try:
            df = get_xrefs_df(prefix)  # FIXME encase this logic in pyobo.get
        except (NoOboFoundry, MissingOboBuild):
            continue
        except ValueError as e:
            if (
                str(e).startswith('Tag-value pair parsing failed for:\n<?xml version="1.0"?>')
                or str(e).startswith('Tag-value pair parsing failed for:\n<?xml version="1.0" encoding="UTF-8"?>')
            ):
                logger.info('no resource available for %s', prefix)
                continue  # this means that it tried doing parsing on an xml page saying get the fuck out
            logger.warning('could not successfully parse %s: %s', prefix, e)
            continue

        df['source'] = prefix
        yield df

        prefix_directory = get_prefix_directory(prefix)
        if not os.listdir(prefix_directory):
            os.rmdir(prefix_directory)

    yield from iter_sourced_xref_dfs()


def _iterate_metaregistry():
    for prefix, _entry in sorted(get_metaregistry().items()):
        if prefix not in SKIP:
            yield prefix, _entry


def _iter_ooh_na_na(leave: bool = False) -> Iterable[Tuple[str, str, str]]:
    """Iterate over all prefix-identifier-name triples we can get.

    :param leave: should the tqdm be left behind?
    """
    for prefix in sorted(get_metaregistry()):
        if prefix in SKIP:
            continue
        try:
            id_name_mapping = get_id_name_mapping(prefix)
        except (NoOboFoundry, MissingOboBuild):
            continue
        except ValueError as e:
            if (
                str(e).startswith('Tag-value pair parsing failed for:\n<?xml version="1.0"?>')
                or str(e).startswith('Tag-value pair parsing failed for:\n<?xml version="1.0" encoding="UTF-8"?>')
            ):
                logger.info('no resource available for %s. See http://www.obofoundry.org/ontology/%s', prefix, prefix)
                continue  # this means that it tried doing parsing on an xml page saying get the fuck out
            logger.warning('could not successfully parse %s: %s', prefix, e)
        else:
            for identifier, name in tqdm(id_name_mapping.items(), desc=f'iterating {prefix}', leave=leave):
                yield prefix, identifier, name

    ncbi_path = ensure_path(ncbigene.PREFIX, ncbigene.GENE_INFO_URL)
    with gzip.open(ncbi_path, 'rt') as file:
        next(file)  # throw away the header
        for line in tqdm(file, desc='extracting ncbigene'):
            line = line.split('\t')
            yield 'ncbigene', line[1], line[2]
