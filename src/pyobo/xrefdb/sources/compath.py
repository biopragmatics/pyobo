# -*- coding: utf-8 -*-

"""Import ComPath mappings between pathways."""

from typing import Iterable

import pandas as pd
from pystow.utils import get_commit

from pyobo.constants import PROVENANCE, SOURCE_ID, SOURCE_PREFIX, TARGET_ID, TARGET_PREFIX, XREF_COLUMNS

__all__ = [
    'iter_compath_dfs',
]


def _get_df(name: str, *, sha: str, sep: str = ',') -> pd.DataFrame:
    url = f'https://raw.githubusercontent.com/ComPath/compath-resources/{sha}/mappings/{name}'
    df = pd.read_csv(
        url,
        sep=sep,
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
    sha = get_commit('ComPath', 'compath-resources')

    yield _get_df('kegg_reactome.csv', sha=sha)
    yield _get_df('kegg_wikipathways.csv', sha=sha)
    yield _get_df('pathbank_kegg.csv', sha=sha)
    yield _get_df('pathbank_reactome.csv', sha=sha)
    yield _get_df('pathbank_wikipathways.csv', sha=sha)
    yield _get_df('special_mappings.csv', sha=sha)
    yield _get_df('wikipathways_reactome.csv', sha=sha)


def get_compath_xrefs_df() -> pd.DataFrame:
    """Iterate over all ComPath mappings."""
    return pd.concat(iter_compath_dfs())


if __name__ == '__main__':
    print(get_compath_xrefs_df().head())
