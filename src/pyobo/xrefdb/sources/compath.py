# -*- coding: utf-8 -*-

"""Import ComPath mappings between pathways."""

from typing import Iterable

import pandas as pd

from ...constants import PROVENANCE, SOURCE_ID, SOURCE_PREFIX, TARGET_ID, TARGET_PREFIX, XREF_COLUMNS

__all__ = [
    'iter_compath_dfs',
]

BASE_URL = 'https://raw.githubusercontent.com/ComPath/compath-resources/master/mappings'


def _get_df(name) -> pd.DataFrame:
    url = f'{BASE_URL}/{name}'
    df = pd.read_csv(
        url, sep=',',
        usecols=['Source Resource', 'Source ID', 'Mapping Type', 'Target Resource', 'Target ID'],
    )
    df.rename(
        columns={
            'Source Resource': SOURCE_PREFIX,
            'Source ID': SOURCE_ID,
            'Target Resource': TARGET_PREFIX,
            'Target ID': TARGET_ID,
        },
        inplace=True,
    )
    df = df[df['Mapping Type'] == 'equivalentTo']
    del df['Mapping Type']
    df[PROVENANCE] = url
    df = df[XREF_COLUMNS]
    return df


def iter_compath_dfs() -> Iterable[pd.DataFrame]:
    """Iterate over all ComPath mappings."""
    yield _get_df('kegg_reactome.csv')
    yield _get_df('kegg_wikipathways.csv')
    yield _get_df('pathbank_kegg.csv')
    yield _get_df('pathbank_reactome.csv')
    yield _get_df('pathbank_wikipathways.csv')
    yield _get_df('special_mappings.csv')
    yield _get_df('wikipathways_reactome.csv')


def get_compath_xrefs_df() -> Iterable[pd.DataFrame]:
    """Iterate over all ComPath mappings."""
    return pd.concat(iter_compath_dfs())
