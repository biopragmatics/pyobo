# -*- coding: utf-8 -*-

"""Sources of xrefs not from OBO."""

from typing import Iterable

import pandas as pd

from .cbms2019 import get_cbms2019_xrefs_df
from .famplex import get_famplex_xrefs_df
from .gilda import get_gilda_xrefs_df
from .intact_complexportal import get_intact_complex_portal_xrefs_df

__all__ = [
    'get_famplex_xrefs_df',
    'get_gilda_xrefs_df',
    'get_cbms2019_xrefs_df',
    'get_intact_complex_portal_xrefs_df',
    'iter_sourced_xref_dfs',
]


def iter_sourced_xref_dfs() -> Iterable[pd.DataFrame]:
    """Iterate all sourced xref dataframes."""
    yield get_gilda_xrefs_df()
    yield get_cbms2019_xrefs_df()
    yield get_famplex_xrefs_df()
    yield get_intact_complex_portal_xrefs_df()
