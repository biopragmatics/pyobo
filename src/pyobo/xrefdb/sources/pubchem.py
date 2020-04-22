# -*- coding: utf-8 -*-

"""Get xrefs from PubChem Compound to MeSH."""

import pandas as pd

from ...sources.pubchem import CID_MESH_URL, get_pubchem_id_to_mesh_id

__all__ = [
    'get_pubchem_mesh_df',
]


def get_pubchem_mesh_df() -> pd.DataFrame:
    """Get PubChem Compound-MeSH xrefs."""
    return pd.DataFrame(
        [
            ('pubchem.compound', k, 'mesh', v, CID_MESH_URL)
            for k, v in get_pubchem_id_to_mesh_id().items()
        ],
        columns=['source_ns', 'source_id', 'target_ns', 'target_id', 'source'],
    )
