# -*- coding: utf-8 -*-

"""Get famplex xrefs"""

import pandas as pd

__all__ = [
    'get_famplex_xrefs',
]

URL = 'https://github.com/sorgerlab/famplex/raw/master/equivalences.csv'


def get_famplex_xrefs() -> pd.DataFrame:
    """Get xrefs from FamPlex."""
    df = pd.read_csv(URL, header=None, names=['target_ns', 'target_id', 'source_id'])
    df['source_ns'] = 'fplx'
    df['source'] = 'https://github.com/sorgerlab/famplex/raw/master/equivalences.csv'
    df = df[['source_ns', 'source_id', 'target_ns', 'target_id', 'source']]
    return df
