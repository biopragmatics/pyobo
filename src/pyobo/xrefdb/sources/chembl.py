# -*- coding: utf-8 -*-

"""Get ChEMBL xrefs."""

from typing import Optional

import bioversions
import pandas as pd

from pyobo.constants import (
    PROVENANCE,
    SOURCE_ID,
    SOURCE_PREFIX,
    TARGET_ID,
    TARGET_PREFIX,
    XREF_COLUMNS,
)
from pyobo.utils.path import ensure_df

CHEMBL_COMPOUND_PREFIX = "chembl.compound"
CHEMBL_TARGET_PREFIX = "chembl.target"


def get_chembl_compound_equivalences_raw(
    usecols=None, version: Optional[str] = None
) -> pd.DataFrame:
    """Get the chemical representations raw dataframe."""
    if version is None:
        version = bioversions.get_version("chembl")

    base_url = f"ftp://ftp.ebi.ac.uk/pub/databases/chembl/ChEMBLdb/releases/chembl_{version}"
    url = f"{base_url}/chembl_{version}_chemreps.txt.gz"
    return ensure_df(CHEMBL_COMPOUND_PREFIX, url=url, sep="\t", usecols=usecols)


def get_chembl_compound_equivalences(version: Optional[str] = None) -> pd.DataFrame:
    """Get ChEMBL chemical equivalences."""
    if version is None:
        version = bioversions.get_version("chembl")

    df = get_chembl_compound_equivalences_raw(version=version)
    rows = []
    for chembl, smiles, inchi, inchi_key in df.values:
        rows.extend(
            [
                ("chembl.compound", chembl, "smiles", smiles, f"chembl{version}"),
                ("chembl.compound", chembl, "inchi", inchi, f"chembl{version}"),
                ("chembl.compound", chembl, "inchikey", inchi_key, f"chembl{version}"),
            ]
        )
    return pd.DataFrame(rows, columns=XREF_COLUMNS)


def get_chembl_protein_equivalences(version: Optional[str] = None) -> pd.DataFrame:
    """Get ChEMBL protein equivalences."""
    if version is None:
        version = bioversions.get_version("chembl")

    url = f"ftp://ftp.ebi.ac.uk/pub/databases/chembl/ChEMBLdb/releases/chembl_{version}/chembl_uniprot_mapping.txt"
    df = ensure_df(
        CHEMBL_TARGET_PREFIX,
        url=url,
        sep="\t",
        usecols=[0, 1],
        names=[TARGET_ID, SOURCE_ID],  # switch around
    )
    df.loc[:, SOURCE_PREFIX] = "chembl.target"
    df.loc[:, TARGET_PREFIX] = "uniprot"
    df.loc[:, PROVENANCE] = f"chembl{version}"
    df = df[XREF_COLUMNS]
    return df


def get_chembl_xrefs_df(version: Optional[str] = None) -> pd.DataFrame:
    """Get all ChEBML equivalences."""
    if version is None:
        version = bioversions.get_version("chembl")

    return pd.concat(
        [
            get_chembl_compound_equivalences(version=version),
            get_chembl_protein_equivalences(version=version),
        ]
    )
