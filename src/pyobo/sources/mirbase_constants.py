# -*- coding: utf-8 -*-

"""Constants for miRBase."""

import pandas as pd

from ..path_utils import ensure_df

PREFIX = 'mirbase'
VERSION = '22.1'

PREFAM_URL = f'ftp://mirbase.org/pub/mirbase/{VERSION}/database_files/mirna_prefam.txt.gz'
PREMATURE_TO_PREFAMILY_URL = f'ftp://mirbase.org/pub/mirbase/{VERSION}/database_files/mirna_2_prefam.txt.gz'
PREMATURE_URL = f'ftp://mirbase.org/pub/mirbase/{VERSION}/database_files/mirna.txt.gz'
MATURE_URL = f'ftp://mirbase.org/pub/mirbase/{VERSION}/database_files/mirna_mature.txt.gz'
PREMATURE_TO_MATURE = f'ftp://mirbase.org/pub/mirbase/{VERSION}/database_files/mirna_pre_mature.txt.gz'


def get_premature_family_df() -> pd.DataFrame:
    """Get premature family dataframe."""
    return ensure_df(
        PREFIX, PREFAM_URL, version=VERSION,
        names=['prefamily_key', 'family_id', 'family_name'],
        usecols=[0, 1, 2],
        index_col=0,
        dtype=str,
    )


def get_premature_to_prefamily_df() -> pd.DataFrame:
    """Get premature miRNA to premature family dataframe."""
    return ensure_df(
        PREFIX, PREMATURE_TO_PREFAMILY_URL, version=VERSION,
        names=['premature_key', 'prefamily_key'],
        dtype=str,
    )


def get_premature_df() -> pd.DataFrame:
    """Get premature miRNA dataframe."""
    return ensure_df(
        PREFIX, PREMATURE_URL, version=VERSION,
        names=['premature_key', 'mirbase_id', 'mirna_name'],
        usecols=[0, 1, 2],
        index_col=0,
        dtype=str,
    )


def get_mature_df() -> pd.DataFrame:
    """Get mature miRNA dataframe."""
    return ensure_df(
        PREFIX, MATURE_URL, version=VERSION,
        names=[
            'mature_key',
            'name',
            'previous',
            'mirbase.mature_id',
        ],
        usecols=[0, 1, 2, 3],
        index_col=0,
        dtype=str,
    )
