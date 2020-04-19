# -*- coding: utf-8 -*-

"""Cross references from Gilda.

.. seealso:: https://github.com/indralabs/gilda
"""

import pandas as pd

from pyobo.identifier_utils import normalize_prefix

__all__ = [
    'get_gilda_xrefs_df',
]

GILDA_MAPPINGS = 'https://raw.githubusercontent.com/indralab/gilda/master/gilda/resources/mesh_mappings.tsv'


def get_gilda_xrefs_df() -> pd.DataFrame:
    """Get xrefs from Gilda."""
    df = pd.read_csv(
        GILDA_MAPPINGS,
        sep='\t',
        header=None,
        usecols=[0, 1, 3, 4],
        names=['source_ns', 'source_id', 'target_ns', 'target_id'],
    )
    df['source'] = GILDA_MAPPINGS

    for k in 'source_ns', 'target_ns':
        df[k] = df[k].map(normalize_prefix)

    for k in 'source_id', 'target_id':
        df[k] = df[k].map(_fix_gogo)

    return df


def _fix_gogo(s):
    for prefix in ('CHEBI:', 'DOID:', 'HP:', 'GO:'):
        if s.startswith(prefix):
            return s[len(prefix):]
    return s
