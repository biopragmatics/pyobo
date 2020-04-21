# -*- coding: utf-8 -*-

"""Import ComPath mappings between pathways."""

from typing import Iterable

import pandas as pd

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
            'Source Resource': 'source_ns',
            'Source ID': 'source_id',
            'Target Resource': 'target_ns',
            'Target ID': 'target_id',
        },
        inplace=True,
    )
    df = df[df['Mapping Type'] == 'equivalentTo']
    del df['Mapping Type']
    df['source'] = url
    return df[['source_ns', 'source_id', 'target_ns', 'target_id', 'source']]


def iter_compath_dfs() -> Iterable[pd.DataFrame]:
    """Iterate over all ComPath mappings."""
    yield _get_df('kegg_reactome.csv')
    yield _get_df('kegg_wikipathways.csv')
    yield _get_df('pathbank_kegg.csv')
    yield _get_df('pathbank_reactome.csv')
    yield _get_df('pathbank_wikipathways.csv')
    yield _get_df('special_mappings.csv')
    yield _get_df('wikipathways_reactome.csv')
