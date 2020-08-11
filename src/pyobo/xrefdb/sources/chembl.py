# -*- coding: utf-8 -*-

"""Get ChEMBL xrefs."""

import pandas as pd

from pyobo.path_utils import ensure_df

PREFIX = 'chembl.compound'
TARGET_PREFIX = 'chembl.target'
VERSION = '27'

BASE = f'ftp://ftp.ebi.ac.uk/pub/databases/chembl/ChEMBLdb/releases/chembl_{VERSION}'
CHEMICALS = f'{BASE}/chembl_{VERSION}_chemreps.txt.gz'
PROTEINS = f'{BASE}/chembl_uniprot_mapping.txt'


def get_chembl_compound_equivalences() -> pd.DataFrame:
    """Get ChEMBL chemical equivalences."""
    df = ensure_df(PREFIX, CHEMICALS, sep='\t')
    rows = []
    for chembl, smiles, inchi, inchi_key in df.values:
        rows.extend([
            ('chembl.compound', chembl, 'smiles', smiles, f'chembl{VERSION}'),
            ('chembl.compound', chembl, 'inchi', inchi, f'chembl{VERSION}'),
            ('chembl.compound', chembl, 'inchikey', inchi_key, f'chembl{VERSION}'),
        ])
    return pd.DataFrame(
        rows, columns=['source_ns', 'source_id', 'target_ns', 'target_id', 'source'],
    )


def get_chembl_protein_equivalences() -> pd.DataFrame:
    """Get ChEMBL protein equivalences."""
    df = ensure_df(
        TARGET_PREFIX,
        PROTEINS,
        sep='\t',
        usecols=[0, 1],
        names=['target_id', 'source_id'],  # switch around
    )
    df.loc[:, 'source_ns'] = 'chembl.target'
    df.loc[:, 'target_ns'] = 'uniprot'
    df.loc[:, 'source'] = f'chembl{VERSION}'
    df = df[['source_ns', 'source_id', 'target_ns', 'target_id', 'source']]
    return df


if __name__ == '__main__':
    get_chembl_compound_equivalences()
    get_chembl_protein_equivalences()
