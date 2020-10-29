# -*- coding: utf-8 -*-

"""Get ChEMBL xrefs."""

import pandas as pd

from pyobo.constants import PROVENANCE, SOURCE_ID, SOURCE_PREFIX, TARGET_ID, TARGET_PREFIX, XREF_COLUMNS
from pyobo.path_utils import ensure_df

CHEMBL_COMPOUND_PREFIX = 'chembl.compound'
CHEMBL_TARGET_PREFIX = 'chembl.target'
VERSION = '27'

BASE = f'ftp://ftp.ebi.ac.uk/pub/databases/chembl/ChEMBLdb/releases/chembl_{VERSION}'
CHEMICALS = f'{BASE}/chembl_{VERSION}_chemreps.txt.gz'
PROTEINS = f'{BASE}/chembl_uniprot_mapping.txt'


def get_chembl_compound_equivalences_raw(usecols=None) -> pd.DataFrame:
    """Get the chemical representations raw dataframe."""
    return ensure_df(CHEMBL_COMPOUND_PREFIX, CHEMICALS, sep='\t', usecols=usecols)


def get_chembl_compound_equivalences() -> pd.DataFrame:
    """Get ChEMBL chemical equivalences."""
    df = get_chembl_compound_equivalences_raw()
    rows = []
    for chembl, smiles, inchi, inchi_key in df.values:
        rows.extend([
            ('chembl.compound', chembl, 'smiles', smiles, f'chembl{VERSION}'),
            ('chembl.compound', chembl, 'inchi', inchi, f'chembl{VERSION}'),
            ('chembl.compound', chembl, 'inchikey', inchi_key, f'chembl{VERSION}'),
        ])
    return pd.DataFrame(rows, columns=XREF_COLUMNS)


def get_chembl_protein_equivalences() -> pd.DataFrame:
    """Get ChEMBL protein equivalences."""
    df = ensure_df(
        CHEMBL_TARGET_PREFIX,
        PROTEINS,
        sep='\t',
        usecols=[0, 1],
        names=[TARGET_ID, SOURCE_ID],  # switch around
    )
    df.loc[:, SOURCE_PREFIX] = 'chembl.target'
    df.loc[:, TARGET_PREFIX] = 'uniprot'
    df.loc[:, PROVENANCE] = f'chembl{VERSION}'
    df = df[XREF_COLUMNS]
    return df


def get_chembl_xrefs_df() -> pd.DataFrame:
    """Get all ChEBML equivalences."""
    return pd.concat([
        get_chembl_compound_equivalences(),
        get_chembl_protein_equivalences(),
    ])
