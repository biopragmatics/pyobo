# -*- coding: utf-8 -*-

"""Get the xrefs from IntAct."""

from typing import Mapping

import pandas as pd

from pyobo.cache_utils import cached_mapping
from pyobo.path_utils import prefix_directory_join

__all__ = [
    'COMPLEXPORTAL_MAPPINGS',
    'get_intact_complex_portal_xrefs_df',
    'get_complexportal_mapping',
    'get_intact_reactome_xrefs_df',
    'get_reactome_mapping',
]

COMPLEXPORTAL_MAPPINGS = 'ftp://ftp.ebi.ac.uk/pub/databases/intact/current/various/cpx_ebi_ac_translation.txt'
REACTOME_MAPPINGS = 'ftp://ftp.ebi.ac.uk/pub/databases/intact/current/various/reactome.dat'


def _get_complexportal_df():
    return pd.read_csv(COMPLEXPORTAL_MAPPINGS, sep='\t', header=None, names=['source_id', 'target_id'])


def get_intact_complex_portal_xrefs_df() -> pd.DataFrame:
    """Get IntAct-Complex Portal xrefs."""
    df = _get_complexportal_df()
    df['source_ns'] = 'intact'
    df['target_ns'] = 'complexportal'
    df['source'] = COMPLEXPORTAL_MAPPINGS
    df = df[['source_ns', 'source_id', 'target_ns', 'target_id', 'source']]
    return df


@cached_mapping(
    path=prefix_directory_join('intact', 'cache', 'xrefs', 'complexportal.tsv'),
    header=['intact_id', 'complexportal_id'],
)
def get_complexportal_mapping() -> Mapping[str, str]:
    """Get IntAct to Complex Portal mapping.

    Is basically equivalent to:

    .. code-block:: python

        from pyobo import get_filtered_xrefs
        intact_complexportal_mapping = get_filtered_xrefs('intact', 'complexportal')
    """
    df = _get_complexportal_df()
    return dict(df.values)


def _get_reactome_df():
    return pd.read_csv(REACTOME_MAPPINGS, sep='\t', header=None, names=['source_id', 'target_id'])


def get_intact_reactome_xrefs_df() -> pd.DataFrame:
    """Get IntAct-Reactome xrefs."""
    df = _get_reactome_df()
    df['source_ns'] = 'intact'
    df['target_ns'] = 'reactome'
    df['source'] = REACTOME_MAPPINGS
    df = df[['source_ns', 'source_id', 'target_ns', 'target_id', 'source']]
    return df


@cached_mapping(
    path=prefix_directory_join('intact', 'cache', 'xrefs', 'reactome.tsv'),
    header=['intact_id', 'reactome_id'],
)
def get_reactome_mapping() -> Mapping[str, str]:
    """Get IntAct to Reactome mapping.

    Is basically equivalent to:

    .. code-block:: python

        from pyobo import get_filtered_xrefs
        intact_complexportal_mapping = get_filtered_xrefs('intact', 'reactome')
    """
    df = _get_complexportal_df()
    return dict(df.values)
