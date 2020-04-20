# -*- coding: utf-8 -*-

"""Get FamPlex xrefs."""

import logging
from typing import Mapping, Tuple

import pandas as pd

from pyobo.identifier_utils import normalize_prefix

__all__ = [
    'get_famplex_xrefs_df',
]

logger = logging.getLogger(__name__)

URL = 'https://github.com/sorgerlab/famplex/raw/master/equivalences.csv'


def _get_df() -> pd.DataFrame:
    return pd.read_csv(URL, header=None, names=['target_ns', 'target_id', 'source_id'])


def get_famplex_xrefs_df() -> pd.DataFrame:
    """Get xrefs from FamPlex."""
    df = _get_df()
    df['source_ns'] = 'fplx'
    df['source'] = 'https://github.com/sorgerlab/famplex/raw/master/equivalences.csv'
    df = df[['source_ns', 'source_id', 'target_ns', 'target_id', 'source']]
    return df


def get_remapping() -> Mapping[Tuple[str, str], Tuple[str, str, str]]:
    """Get a mapping from database/identifier pairs to famplex identifiers."""
    df = _get_df()
    rv = {}
    for target_ns, target_id, source_id in df.values:
        remapped_prefix = normalize_prefix(target_ns)
        if remapped_prefix is None:
            logger.debug('could not remap %s', target_ns)
        else:
            rv[remapped_prefix, target_id] = 'fplx', source_id, source_id
    return rv


if __name__ == '__main__':
    from pprint import pprint
    pprint(get_remapping())
