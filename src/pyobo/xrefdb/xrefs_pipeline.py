# -*- coding: utf-8 -*-

"""Pipeline for extracting all xrefs from OBO documents available."""

import gzip
import itertools as itt
import logging
import os
import time
from typing import Iterable, Optional, Tuple

import bioregistry
import click
import networkx as nx
import pandas as pd
from more_click import verbose_option
from tqdm import tqdm

from .obo_xrefs import iterate_obo_xrefs
from .sources import iter_xref_plugins
from ..api import (
    get_hierarchy, get_id_definition_mapping, get_id_name_mapping, get_id_synonyms_mapping, get_id_to_alts,
    get_properties_df, get_relations_df, get_typedef_df,
)
from ..constants import DATABASE_DIRECTORY, PROVENANCE, SOURCE_ID, SOURCE_PREFIX, TARGET_ID, TARGET_PREFIX, XREF_COLUMNS
from ..getters import SKIP, iter_helper, iter_helper_helper
from ..sources import ncbigene, pubchem
from ..utils.path import ensure_path

logger = logging.getLogger(__name__)


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


def get_xref_df(
    *,
    force: bool = False,
    use_tqdm: bool = True,
    skip_below=None,
    strict: bool = True,
) -> pd.DataFrame:
    """Get the ultimate xref database."""
    df = pd.concat(_iterate_xref_dfs(force=force, use_tqdm=use_tqdm, skip_below=skip_below, strict=strict))

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

    return df


def _iterate_xref_dfs(
    *,
    force: bool = False,
    use_tqdm: bool = True,
    skip_below: Optional[str] = None,
    strict: bool = True,
) -> Iterable[pd.DataFrame]:
    yield from iterate_obo_xrefs(use_tqdm=use_tqdm, force=force, skip_below=skip_below, strict=strict)
    yield from iter_xref_plugins(skip_below=skip_below)


def _iter_ncbigene(left, right):
    ncbi_path = ensure_path(ncbigene.PREFIX, url=ncbigene.GENE_INFO_URL)
    with gzip.open(ncbi_path, 'rt') as file:
        next(file)  # throw away the header
        for line in tqdm(file, desc=f'extracting {ncbigene.PREFIX}', unit_scale=True, total=27_000_000):
            line = line.strip().split('\t')
            yield ncbigene.PREFIX, line[left], line[right]


def _iter_ooh_na_na(leave: bool = False, **kwargs) -> Iterable[Tuple[str, str, str]]:
    """Iterate over all prefix-identifier-name triples we can get.

    :param leave: should the tqdm be left behind?
    """
    yield from iter_helper(get_id_name_mapping, leave=leave, **kwargs)
    yield from _iter_ncbigene(1, 2)

    pcc_path = pubchem._ensure_cid_name_path()
    with gzip.open(pcc_path, mode='rt', encoding='ISO-8859-1') as file:
        for line in tqdm(file, desc=f'extracting {pubchem.PREFIX}', unit_scale=True, total=103_000_000):
            identifier, name = line.strip().split('\t', 1)
            yield pubchem.PREFIX, identifier, name


def _iter_definitions(leave: bool = False, **kwargs) -> Iterable[Tuple[str, str, str]]:
    """Iterate over all prefix-identifier-descriptions triples we can get."""
    yield from iter_helper(get_id_definition_mapping, leave=leave, **kwargs)
    yield from _iter_ncbigene(1, 8)


def _iter_alts(leave: bool = False, strict: bool = True, **kwargs) -> Iterable[Tuple[str, str, str]]:
    for prefix, identifier, alts in iter_helper(get_id_to_alts, leave=leave, strict=strict, **kwargs):
        for alt in alts:
            yield prefix, identifier, alt


def _iter_synonyms(leave: bool = False, **kwargs) -> Iterable[Tuple[str, str, str]]:
    """Iterate over all prefix-identifier-synonym triples we can get.

    :param leave: should the tqdm be left behind?
    """
    for prefix, identifier, synonyms in iter_helper(get_id_synonyms_mapping, leave=leave, **kwargs):
        for synonym in synonyms:
            yield prefix, identifier, synonym


def _iter_typedefs(**kwargs) -> Iterable[Tuple[str, str, str, str]]:
    """Iterate over all prefix-identifier-name triples we can get."""
    for prefix, df in iter_helper_helper(get_typedef_df, **kwargs):
        for t in df.values:
            yield (prefix, *t)


def _iter_relations(**kwargs) -> Iterable[Tuple[str, str, str, str, str, str]]:
    for prefix, df in iter_helper_helper(get_relations_df, **kwargs):
        for t in df.values:
            yield (prefix, *t)


def _iter_properties(**kwargs) -> Iterable[Tuple[str, str, str, str]]:
    for prefix, df in iter_helper_helper(get_properties_df, **kwargs):
        for t in df.values:
            yield (prefix, *t)
