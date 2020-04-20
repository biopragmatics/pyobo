# -*- coding: utf-8 -*-

"""Get the xrefs from IntAct."""

from typing import Mapping

import pandas as pd

from pyobo.cache_utils import cached_mapping
from pyobo.path_utils import prefix_directory_join

__all__ = [
    'URL',
    'get_intact_complex_portal_xrefs_df',
    'get_complexportal_mapping',
]

URL = 'ftp://ftp.ebi.ac.uk/pub/databases/intact/current/various/cpx_ebi_ac_translation.txt'


def _get_df():
    return pd.read_csv(URL, sep='\t', header=None, names=['source_id', 'target_id'])


def get_intact_complex_portal_xrefs_df() -> pd.DataFrame:
    """Get IntAct-Complex Portal xrefs."""
    df = _get_df()
    df['source_ns'] = 'intact'
    df['target_ns'] = 'complexportal'
    df['source'] = URL
    df = df[['source_ns', 'source_id', 'target_ns', 'target_id', 'source']]
    return df


@cached_mapping(
    path=prefix_directory_join('intact', 'cache', 'xrefs', 'complexportal.tsv'),
    header=[f'intact_id', f'complexportal_id'],
)
def get_complexportal_mapping() -> Mapping[str, str]:
    """Get IntAct to Complex Portal mapping.

    Is basically equivalent to:

    .. code-block:: python

        from pyobo import get_filtered_xrefs
        intact_complexportal_mapping = get_filtered_xrefs('intat', 'complexportal')
    """
    df = _get_df()
    return dict(df.values)
