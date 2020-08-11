# -*- coding: utf-8 -*-

"""Sources of xrefs not from OBO."""

from typing import Iterable

import pandas as pd

from .cbms2019 import get_cbms2019_xrefs_df
from .chembl import get_chembl_compound_equivalences, get_chembl_protein_equivalences
from .compath import iter_compath_dfs
from .famplex import get_famplex_xrefs_df
from .gilda import get_gilda_xrefs_df
from .intact import get_intact_complex_portal_xrefs_df, get_intact_reactome_xrefs_df
from .ncit import iter_ncit_dfs
from .pubchem import get_pubchem_mesh_df
from .wikidata import iterate_wikidata_dfs

__all__ = [
    'get_famplex_xrefs_df',
    'get_gilda_xrefs_df',
    'get_cbms2019_xrefs_df',
    'get_intact_complex_portal_xrefs_df',
    'get_intact_reactome_xrefs_df',
    'iter_sourced_xref_dfs',
    'get_chembl_compound_equivalences',
    'get_chembl_protein_equivalences',
]


def iter_sourced_xref_dfs() -> Iterable[pd.DataFrame]:
    """Iterate all sourced xref dataframes."""
    yield get_gilda_xrefs_df()
    yield get_cbms2019_xrefs_df()
    yield get_famplex_xrefs_df()
    yield get_intact_complex_portal_xrefs_df()
    yield get_intact_reactome_xrefs_df()
    yield from iter_ncit_dfs()
    yield from iter_compath_dfs()
    yield from iterate_wikidata_dfs()
    yield get_pubchem_mesh_df()
    yield get_chembl_compound_equivalences()
    yield get_chembl_protein_equivalences()
