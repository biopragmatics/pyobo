# -*- coding: utf-8 -*-

"""Pipeline for extracting all xrefs from OBO documents available."""

import gzip
import itertools as itt
import logging
import os
import time
from typing import Iterable, Optional, Tuple

import click
import networkx as nx
import pandas as pd
from more_click import verbose_option
from tqdm import tqdm

from .obo_xrefs import iterate_bioregistry, iterate_obo_xrefs
from .sources import iter_xref_plugins
from ..constants import DATABASE_DIRECTORY, PROVENANCE, SOURCE_ID, SOURCE_PREFIX, TARGET_ID, TARGET_PREFIX, XREF_COLUMNS
from ..extract import get_hierarchy, get_id_name_mapping, get_id_synonyms_mapping, get_id_to_alts
from ..getters import iter_helper
from ..path_utils import ensure_path
from ..sources import ncbigene, pubchem

logger = logging.getLogger(__name__)

MAPPINGS_DB_TSV_CACHE = os.path.join(DATABASE_DIRECTORY, 'xrefs.tsv.gz')
MAPPINGS_DB_PKL_CACHE = os.path.join(DATABASE_DIRECTORY, 'xrefs.pkl.gz')
MAPPINGS_DB_SUMMARY_CACHE = os.path.join(DATABASE_DIRECTORY, 'xrefs_summary.tsv')
MAPPINGS_DB_SUMMARY_PROVENANCES_CACHE = os.path.join(DATABASE_DIRECTORY, 'xrefs_summary_provenance.tsv')


# TODO a normal graph can easily be turned into a directed graph where each
#  edge points from low priority to higher priority, then the graph can
#  be reduced to a set of star graphs and ultimately to a single dictionary


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
    for source_ns, source_id, target_ns, target_id, provenance in it:
        rv.add_edge(
            _to_curie(source_ns, source_id),
            _to_curie(target_ns, target_id),
            provenance=provenance,
        )

    return rv


def summarize_xref_df(df: pd.DataFrame) -> pd.DataFrame:
    """Get all meta-mappings."""
    return _summarize(df, [SOURCE_PREFIX, TARGET_PREFIX])


def summarize_xref_provenances_df(df: pd.DataFrame) -> pd.DataFrame:
    """Get all meta-mappings."""
    return _summarize(df, [SOURCE_PREFIX, TARGET_PREFIX, PROVENANCE])


def _summarize(df: pd.DataFrame, columns) -> pd.DataFrame:
    """Get all meta-mappings."""
    rv = df[columns].groupby(columns).size().reset_index()
    rv.columns = [*columns, 'count']
    rv.sort_values('count', inplace=True, ascending=False)
    return rv


def _to_curie(prefix: str, identifier: str) -> str:
    return f'{prefix}:{identifier}'


def get_xref_df(*, force: bool = False, use_tqdm: bool = True, skip_below=None) -> pd.DataFrame:
    """Get the ultimate xref database."""
    if not force and os.path.exists(MAPPINGS_DB_TSV_CACHE):
        logger.info('loading cached mapping database from %s', MAPPINGS_DB_TSV_CACHE)
        t = time.time()
        rv = pd.read_csv(MAPPINGS_DB_TSV_CACHE, sep='\t', dtype=str)
        logger.info('loaded in %.2fs', time.time() - t)
        return rv

    df = pd.concat(_iterate_xref_dfs(force=force, use_tqdm=use_tqdm, skip_below=skip_below))

    logger.info('sorting xrefs')
    sort_start = time.time()
    df.sort_values(XREF_COLUMNS, inplace=True)
    logger.info('sorted in %.2fs', time.time() - sort_start)

    logger.info('dropping duplicates')
    drop_duplicate_start = time.time()
    df.drop_duplicates(inplace=True)
    logger.info('dropped duplicates in %.2fs', time.time() - drop_duplicate_start)

    logger.info('dropping NA')
    drop_na_start = time.time()
    df.dropna(inplace=True)
    logger.info('dropped NAs in %.2fs', time.time() - drop_na_start)

    logger.info('writing mapping database to %s', MAPPINGS_DB_TSV_CACHE)
    t = time.time()
    df.to_csv(MAPPINGS_DB_TSV_CACHE, sep='\t', index=False)
    logger.info('wrote in %.2fs', time.time() - t)

    logger.info('writing mapping database to %s', MAPPINGS_DB_PKL_CACHE)
    t = time.time()
    df.to_pickle(MAPPINGS_DB_PKL_CACHE)
    logger.info('wrote in %.2fs', time.time() - t)

    logger.info('making mapping summary')
    t = time.time()
    summary_df = summarize_xref_df(df)
    logger.info('made mapping summary in %.2fs', time.time() - t)
    summary_df.to_csv(MAPPINGS_DB_SUMMARY_CACHE, index=False, sep='\t')

    logger.info('making provenance summary')
    t = time.time()
    xref_provenances_df = summarize_xref_provenances_df(df)
    logger.info('made provenance summary in %.2fs', time.time() - t)
    xref_provenances_df.to_csv(MAPPINGS_DB_SUMMARY_PROVENANCES_CACHE, index=False, sep='\t')

    return df


def _iterate_xref_dfs(
    *,
    force: bool = False,
    use_tqdm: bool = True,
    skip_below: Optional[str] = None,
) -> Iterable[pd.DataFrame]:
    yield from iterate_obo_xrefs(use_tqdm=use_tqdm, force=force, skip_below=skip_below)
    yield from iter_xref_plugins(skip_below=skip_below)


def _iter_ooh_na_na(leave: bool = False) -> Iterable[Tuple[str, str, str]]:
    """Iterate over all prefix-identifier-name triples we can get.

    :param leave: should the tqdm be left behind?
    """
    yield from iter_helper(get_id_name_mapping, leave=leave)

    ncbi_path = ensure_path(ncbigene.PREFIX, url=ncbigene.GENE_INFO_URL)
    with gzip.open(ncbi_path, 'rt') as file:
        next(file)  # throw away the header
        for line in tqdm(file, desc=f'extracting {ncbigene.PREFIX}', unit_scale=True, total=27_000_000):
            line = line.strip().split('\t')
            yield ncbigene.PREFIX, line[1], line[2]

    pcc_path = pubchem._ensure_cid_name_path()
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


def bens_magical_ontology(use_tqdm: bool = True) -> nx.DiGraph:
    """Make a super graph containing is_a, part_of, and xref relationships."""
    rv = nx.DiGraph()

    logger.info('getting xrefs')
    df = get_xref_df()
    for source_ns, source_id, target_ns, target_id, provenance in df.values:
        rv.add_edge(f'{source_ns}:{source_id}', f'{target_ns}:{target_id}', relation='xref', provenance=provenance)

    logger.info('getting hierarchies')
    for prefix in iterate_bioregistry(use_tqdm=use_tqdm):
        hierarchy = get_hierarchy(prefix, include_has_member=True, include_part_of=True)
        rv.add_edges_from(hierarchy.edges(data=True))

    # TODO include translates_to, transcribes_to, and has_variant

    return rv


@click.command()
@verbose_option
@click.option('--force', is_flag=True)
@click.option('-s', '--skip-below')
def _main(force: bool, skip_below: Optional[str]):
    get_xref_df(force=force, skip_below=skip_below)


if __name__ == '__main__':
    _main()
