# -*- coding: utf-8 -*-

"""Pipeline for extracting all xrefs from OBO documents available."""

import gzip
import itertools as itt
import logging
import os
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Iterable, List, Mapping, Optional, Set, Tuple

import networkx as nx
import pandas as pd
from more_itertools import pairwise
from tqdm import tqdm

from .sources import iter_xref_plugins
from ..constants import DATABASE_DIRECTORY, SOURCE_ID, SOURCE_PREFIX, TARGET_ID, TARGET_PREFIX, XREF_COLUMNS
from ..extract import (
    get_hierarchy, get_id_name_mapping, get_id_synonyms_mapping, get_id_to_alts,
    get_xrefs_df,
)
from ..getters import MissingOboBuild, NoOboFoundry, iter_helper
from ..identifier_utils import get_metaregistry, normalize_prefix
from ..path_utils import ensure_path, get_prefix_directory
from ..sources import ncbigene, pubchem

logger = logging.getLogger(__name__)

SKIP = {
    'obi',
    'ncbigene',  # too big, refs acquired from other dbs
    'pubchem.compound',  # to big, can't deal with this now
    'rnao',  # just really malformed, way too much unconverted OWL
    'gaz',
    'geo',
}
SKIP_XREFS = {
    'mamo', 'ido', 'iao', 'gaz', 'nbo', 'geo',
}

_DEFAULT_PRIORITY_LIST = [
    # Genes
    'ncbigene',
    'hgnc',
    'rgd',
    'mgi',
    'ensembl',
    'uniprot',
    # Chemicals
    # 'inchikey',
    # 'inchi',
    # 'smiles',
    'pubchem.compound',
    'chebi',
    'drugbank',
    'chembl.compound',
    'zinc',
    # protein families and complexes (and famplexes :))
    'complexportal',
    'fplx',
    'ec-code',
    'interpro',
    'pfam',
    'signor',
    # Pathologies/phenotypes
    'mondo',
    'efo',
    'doid',
    'hp',
    # Taxa
    'ncbitaxon',
    # If you can get away from MeSH, do it
    'mesh',
    'icd',
]
DEFAULT_PRIORITY_LIST = []
for _entry in _DEFAULT_PRIORITY_LIST:
    _prefix = normalize_prefix(_entry)
    if not _prefix:
        raise RuntimeError(f'unresolved prefix: {_entry}')
    if _prefix in DEFAULT_PRIORITY_LIST:
        raise RuntimeError(f'duplicate found in priority list: {_entry}/{_prefix}')
    DEFAULT_PRIORITY_LIST.append(_prefix)


# TODO a normal graph can easily be turned into a directed graph where each
#  edge points from low priority to higher priority, then the graph can
#  be reduced to a set of star graphs and ultimately to a single dictionary

@dataclass
class Canonicalizer:
    """Wraps a graph and priority list to allow getting the best identifier."""

    #: A graph from :func:`get_graph_from_xref_df`
    graph: nx.Graph

    #: A list of prefixes. The ones with the lower index are higher priority
    priority: Optional[List[str]] = None

    #: Longest length paths allowed
    cutoff: int = 5

    _priority: Mapping[str, int] = field(init=False)

    def __post_init__(self):
        """Initialize the priority map based on the priority list."""
        if self.priority is None:
            self.priority = DEFAULT_PRIORITY_LIST
        self._priority = {
            entry: len(self.priority) - i
            for i, entry in enumerate(self.priority)
        }

    def _key(self, curie: str) -> Optional[int]:
        prefix = self.graph.nodes[curie]['prefix']
        return self._priority.get(prefix)

    def _get_priority_dict(self, curie: str) -> Mapping[str, int]:
        return dict(self._iterate_priority_targets(curie))

    def _iterate_priority_targets(self, curie: str) -> Iterable[Tuple[str, int]]:
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
        return max(priority_dict, key=priority_dict.get)

    @classmethod
    def get_default(cls, priority: Optional[Iterable[str]] = None) -> 'Canonicalizer':
        """Get the default canonicalizer."""
        if priority is not None:
            priority = tuple(priority)
        return cls._get_default_helper(priority=priority)

    @classmethod
    @lru_cache()
    def _get_default_helper(cls, priority: Optional[Tuple[str, ...]] = None) -> 'Canonicalizer':
        """Help get the default canonicalizer."""
        graph = cls._get_default_graph()
        return cls(graph=graph, priority=list(priority) if priority else None)

    @staticmethod
    @lru_cache()
    def _get_default_graph() -> nx.Graph:
        df = get_xref_df(use_cached=True)
        graph = get_graph_from_xref_df(df)
        return graph

    def iterate_flat_mapping(self, use_tqdm: bool = True) -> Iterable[Tuple[str, str]]:
        """Iterate over the canonical mapping from all nodes to their canonical CURIEs."""
        nodes = self.graph.nodes()
        if use_tqdm:
            nodes = tqdm(
                nodes,
                total=self.graph.number_of_nodes(),
                desc='building flat mapping',
                unit_scale=True,
                unit='CURIE',
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
    ) -> Optional[Mapping[str, List[Mapping[str, str]]]]:
        """Get all shortest paths between given entity and its equivalent entities."""
        return single_source_shortest_path(graph=self.graph, curie=curie, cutoff=cutoff)

    def all_shortest_paths(self, source_curie: str, target_curie: str) -> List[List[Mapping[str, str]]]:
        """Get all shortest paths between the two entities."""
        return all_shortest_paths(graph=self.graph, source_curie=source_curie, target_curie=target_curie)

    @classmethod
    def from_df(cls, df: pd.DataFrame) -> 'Canonicalizer':
        """Instantiate from a dataframe."""
        return cls(graph=get_graph_from_xref_df(df))


def get_graph_from_xref_df(df: pd.DataFrame) -> nx.Graph:
    """Generate a graph from the mappings dataframe."""
    rv = nx.Graph()

    it = itt.chain(
        df[[SOURCE_PREFIX, SOURCE_ID]].drop_duplicates().values,
        df[[TARGET_PREFIX, TARGET_ID]].drop_duplicates().values,
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
    c = [SOURCE_PREFIX, TARGET_PREFIX]
    rv = df[c].groupby(c).size().reset_index()
    rv.columns = [SOURCE_PREFIX, TARGET_PREFIX, 'count']
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


def single_source_shortest_path(
    graph: nx.Graph,
    curie: str,
    cutoff: Optional[int] = None,
) -> Optional[Mapping[str, List[Mapping[str, str]]]]:
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
    rv = nx.single_source_shortest_path(graph, curie, cutoff=cutoff)
    return {
        k: [
            dict(source=s, target=t, provenance=graph[s][t]['source'])
            for s, t in pairwise(v)
        ]
        for k, v in rv.items()
        if k != curie  # don't map to self
    }


XREF_DB_CACHE = os.path.join(DATABASE_DIRECTORY, 'xrefs.tsv.gz')


def get_xref_df(use_cached: bool = False) -> pd.DataFrame:
    """Get the ultimate xref database."""
    if use_cached and os.path.exists(XREF_DB_CACHE):
        return pd.read_csv(XREF_DB_CACHE, sep='\t', dtype=str)

    df = pd.concat(_iterate_xref_dfs())
    df.drop_duplicates(inplace=True)
    df.dropna(inplace=True)
    df.sort_values(XREF_COLUMNS, inplace=True)

    if use_cached:
        df.to_csv(XREF_DB_CACHE, sep='\t', index=False)

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

    yield from iter_xref_plugins()


def _iterate_metaregistry():
    for prefix, _entry in sorted(get_metaregistry().items()):
        if prefix not in SKIP:
            yield prefix, _entry


def _iter_ooh_na_na(leave: bool = False) -> Iterable[Tuple[str, str, str]]:
    """Iterate over all prefix-identifier-name triples we can get.

    :param leave: should the tqdm be left behind?
    """
    yield from iter_helper(get_id_name_mapping, leave=leave)

    ncbi_path = ensure_path(ncbigene.PREFIX, ncbigene.GENE_INFO_URL)
    with gzip.open(ncbi_path, 'rt') as file:
        next(file)  # throw away the header
        for line in tqdm(file, desc=f'extracting {ncbigene.PREFIX}', unit_scale=True, total=27_000_000):
            line = line.strip().split('\t')
            yield ncbigene.PREFIX, line[1], line[2]

    pcc_path = ensure_path(pubchem.PREFIX, pubchem.CID_NAME_URL)
    with gzip.open(pcc_path, mode='rt', encoding='ISO-8859-1') as file:
        for line in tqdm(file, desc=f'extracting {pubchem.PREFIX}', unit_scale=True, total=103_000_000):
            identifier, name = line.strip().split('\t', 1)
            yield pubchem.PREFIX, identifier, name


def _iter_alts(leave: bool = False) -> Iterable[Tuple[str, str, str]]:
    for prefix, identifier, alts in iter_helper(get_id_to_alts, leave=leave):
        for alt in alts:
            yield prefix, identifier, alt


def _iter_synonyms(leave: bool = False) -> Iterable[Tuple[str, str, str]]:
    """Iterate over all prefix-identifier-synonym triples we can get.

    :param leave: should the tqdm be left behind?
    """
    for prefix, identifier, synonyms in iter_helper(get_id_synonyms_mapping, leave=leave):
        for synonym in synonyms:
            yield prefix, identifier, synonym


def bens_magical_ontology() -> nx.DiGraph:
    """Make a super graph containing is_a, part_of, and xref relationships."""
    rv = nx.DiGraph()

    logger.info('getting xrefs')
    df = get_xref_df()
    for source_ns, source_id, target_ns, target_id, provenance in df.values:
        rv.add_edge(f'{source_ns}:{source_id}', f'{target_ns}:{target_id}', relation='xref', provenance=provenance)

    logger.info('getting hierarchies')
    for prefix, _ in _iterate_metaregistry():
        hierarchy = get_hierarchy(prefix, include_has_member=True, include_part_of=True)
        rv.add_edges_from(hierarchy.edges(data=True))

    # TODO include translates_to, transcribes_to, and has_variant

    return rv


def get_equivalent(curie: str, cutoff: Optional[int] = None) -> Set[str]:
    """Get equivalent CURIEs."""
    canonicalizer = Canonicalizer.get_default()
    r = canonicalizer.single_source_shortest_path(curie=curie, cutoff=cutoff)
    return set(r or [])


def get_priority_curie(curie: str) -> str:
    """Get the priority CURIE mapped to the best namespace."""
    canonicalizer = Canonicalizer.get_default()
    return canonicalizer.canonicalize(curie)


def remap_file_stream(file_in, file_out, column: int, sep='\t') -> None:
    """Remap a file."""
    for line in file_in:
        line = line.strip().split(sep)
        line[column] = get_priority_curie(line[column])
        print(*line, sep=sep, file=file_out)
