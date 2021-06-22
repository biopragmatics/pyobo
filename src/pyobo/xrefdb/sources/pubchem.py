# -*- coding: utf-8 -*-

"""Get xrefs from PubChem Compound to MeSH."""

from typing import Optional

import pandas as pd

from ...constants import XREF_COLUMNS
from ...sources.pubchem import _get_pubchem_extras_url, get_pubchem_id_to_mesh_id

__all__ = [
    "get_pubchem_mesh_df",
]


def get_pubchem_mesh_df(version: Optional[str] = None) -> pd.DataFrame:
    """Get PubChem Compound-MeSH xrefs."""
    cid_mesh_url = _get_pubchem_extras_url(version, "CID-MeSH")
    return pd.DataFrame(
        [
            ("pubchem.compound", k, "mesh", v, cid_mesh_url)
            for k, v in get_pubchem_id_to_mesh_id(version=version).items()
        ],
        columns=XREF_COLUMNS,
    )
