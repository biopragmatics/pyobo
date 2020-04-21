# -*- coding: utf-8 -*-

"""Import NCIT mappings."""

from typing import Iterable

import pandas as pd

from ...path_utils import ensure_df

__all__ = [
    'iter_ncit_dfs',
    'get_ncit_go_df',
    'get_ncit_chebi_df',
    'get_ncit_hgnc_df',
    'get_ncit_uniprot_df',
]

PREFIX = 'ncit'

HGNC_MAPPINGS_URL = 'https://ncit.nci.nih.gov/ncitbrowser/ajax?action=' + \
                    'export_mapping&dictionary=NCIt_to_HGNC_Mapping&version=1.0'

GO_MAPPINGS_URL = 'https://ncit.nci.nih.gov/ncitbrowser/ajax?action=' + \
                  'export_mapping&dictionary=GO_to_NCIt_Mapping&version=1.1'

CHEBI_MAPPINGS_URL = 'https://ncit.nci.nih.gov/ncitbrowser/ajax?action=' + \
                     'export_mapping&dictionary=NCIt_to_ChEBI_Mapping&version=1.0'

# url_swissprot = 'https://ncit.nci.nih.gov/ncitbrowser/ajax?action=' \
#                 'export_mapping&uri=https://evs.nci.nih.gov/ftp1/' \
#                 'NCI_Thesaurus/Mappings/NCIt-SwissProt_Mapping.txt'

UNIPROT_MAPPINGS_URL = 'https://evs.nci.nih.gov/ftp1/NCI_Thesaurus/Mappings/NCIt-SwissProt_Mapping.txt'


def iter_ncit_dfs() -> Iterable[pd.DataFrame]:
    """Iterate all NCIT mappings dataframes."""
    yield get_ncit_hgnc_df()
    yield get_ncit_chebi_df()
    yield get_ncit_uniprot_df()
    yield get_ncit_go_df()


def get_ncit_hgnc_df() -> pd.DataFrame:
    """Get NCIT-HGNC mappings.

    In this file, the only association type was mapsTo.
    """
    df = ensure_df(PREFIX, HGNC_MAPPINGS_URL, path='ncit_hgnc.csv', sep=',', usecols=['Source Code', 'Target Code'])
    df.rename(columns={'Source Code': 'source_id', 'Target Code': 'target_id'}, inplace=True)
    df['target_id'] = df['target_id'].map(lambda s: s[len('HGNC:'):])
    df.dropna(inplace=True)

    df['source_ns'] = 'ncit'
    df['target_ns'] = 'hgnc'
    df['source'] = HGNC_MAPPINGS_URL
    return df[['source_ns', 'source_id', 'target_ns', 'target_id', 'source']]


def get_ncit_go_df() -> pd.DataFrame:
    """Get NCIT-GO mappings.

    In this file, the only association type was mapsTo.
    """
    df = ensure_df(PREFIX, GO_MAPPINGS_URL, path='ncit_go.csv', sep=',')
    df.rename(columns={'Source Code': 'target_id', 'Target Code': 'source_id'}, inplace=True)
    df['target_id'] = df['target_id'].map(lambda s: s[len('GO:')])
    df.dropna(inplace=True)

    df['source_ns'] = 'ncit'
    df['target_ns'] = 'go'
    df['source'] = GO_MAPPINGS_URL
    return df[['source_ns', 'source_id', 'target_ns', 'target_id', 'source']]


def get_ncit_chebi_df() -> pd.DataFrame:
    """Get NCIT-ChEBI mappings.

    In this file, the only association type was mapsTo.
    """
    df = ensure_df(PREFIX, CHEBI_MAPPINGS_URL, path='ncit_chebi.csv', sep=',')
    df.rename(columns={'Source Code': 'source_id', 'Target Code': 'target_id'}, inplace=True)
    df['target_id'] = df['target_id'].map(lambda s: s[len('CHEBI:')])
    df.dropna(inplace=True)

    df['source_ns'] = 'ncit'
    df['target_ns'] = 'chebi'
    df['source'] = CHEBI_MAPPINGS_URL
    return df[['source_ns', 'source_id', 'target_ns', 'target_id', 'source']]


def get_ncit_uniprot_df() -> pd.DataFrame:
    """Get NCIT-UniProt mappings.

    In this file, the only association type was mapsTo.
    """
    df = ensure_df(PREFIX, UNIPROT_MAPPINGS_URL, path='ncit_uniprot.csv')
    df.rename(columns={'NCIt Code': 'source_id', 'SwissProt ID': 'target_id'}, inplace=True)
    df['source_ns'] = 'ncit'
    df['target_ns'] = 'uniprot'
    df['source'] = UNIPROT_MAPPINGS_URL
    return df[['source_ns', 'source_id', 'target_ns', 'target_id', 'source']]
