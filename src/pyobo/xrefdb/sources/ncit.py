"""Import NCIT mappings."""

from collections.abc import Iterable

import pandas as pd

from ...constants import (
    PROVENANCE,
    SOURCE_ID,
    SOURCE_PREFIX,
    TARGET_ID,
    TARGET_PREFIX,
    XREF_COLUMNS,
)
from ...utils.path import ensure_df

__all__ = [
    "iter_ncit_dfs",
    "get_ncit_go_df",
    "get_ncit_chebi_df",
    "get_ncit_hgnc_df",
    "get_ncit_uniprot_df",
]

PREFIX = "ncit"

HGNC_MAPPINGS_URL = (
    "https://ncit.nci.nih.gov/ncitbrowser/ajax?action="
    + "export_mapping&dictionary=NCIt_to_HGNC_Mapping&version=1.0"
)

GO_MAPPINGS_URL = (
    "https://ncit.nci.nih.gov/ncitbrowser/ajax?action="
    + "export_mapping&dictionary=GO_to_NCIt_Mapping&version=1.1"
)

CHEBI_MAPPINGS_URL = (
    "https://ncit.nci.nih.gov/ncitbrowser/ajax?action="
    + "export_mapping&dictionary=NCIt_to_ChEBI_Mapping&version=1.0"
)

# url_swissprot = 'https://ncit.nci.nih.gov/ncitbrowser/ajax?action=' \
#                 'export_mapping&uri=https://evs.nci.nih.gov/ftp1/' \
#                 'NCI_Thesaurus/Mappings/NCIt-SwissProt_Mapping.txt'

UNIPROT_MAPPINGS_URL = (
    "https://evs.nci.nih.gov/ftp1/NCI_Thesaurus/Mappings/NCIt-SwissProt_Mapping.txt"
)


def get_ncit_xrefs_df() -> pd.DataFrame:
    """Get all NCIT mappings in a single dataframe."""
    return pd.concat(iter_ncit_dfs())


def iter_ncit_dfs() -> Iterable[pd.DataFrame]:
    """Iterate all NCIT mappings dataframes."""
    yield get_ncit_hgnc_df()
    yield get_ncit_chebi_df()
    yield get_ncit_uniprot_df()
    yield get_ncit_go_df()


def get_ncit_hgnc_df() -> pd.DataFrame:
    """Get NCIT-HGNC mappings.

    In this file, the only association type was mapsTo.
    """
    df = ensure_df(
        PREFIX,
        url=HGNC_MAPPINGS_URL,
        name="ncit_hgnc.csv",
        sep=",",
        usecols=["Source Code", "Target Code"],
    )
    df.rename(columns={"Source Code": SOURCE_ID, "Target Code": TARGET_ID}, inplace=True)
    df[TARGET_ID] = df[TARGET_ID].map(lambda s: s[len("HGNC:") :])
    df.dropna(inplace=True)

    df[SOURCE_PREFIX] = "ncit"
    df[TARGET_PREFIX] = "hgnc"
    df[PROVENANCE] = HGNC_MAPPINGS_URL
    df = df[XREF_COLUMNS]
    return df


def get_ncit_go_df() -> pd.DataFrame:
    """Get NCIT-GO mappings.

    In this file, the only association type was mapsTo.
    """
    df = ensure_df(PREFIX, url=GO_MAPPINGS_URL, name="ncit_go.csv", sep=",")
    # The data is flipped here
    df.rename(columns={"Source Code": TARGET_ID, "Target Code": SOURCE_ID}, inplace=True)
    df[TARGET_ID] = df[TARGET_ID].map(lambda s: s[len("GO:")])
    df.dropna(inplace=True)

    df[SOURCE_PREFIX] = "ncit"
    df[TARGET_PREFIX] = "go"
    df[PROVENANCE] = GO_MAPPINGS_URL
    df = df[XREF_COLUMNS]
    return df


def get_ncit_chebi_df() -> pd.DataFrame:
    """Get NCIT-ChEBI mappings.

    In this file, the only association type was mapsTo.
    """
    df = ensure_df(PREFIX, url=CHEBI_MAPPINGS_URL, name="ncit_chebi.csv", sep=",")
    df.rename(columns={"Source Code": SOURCE_ID, "Target Code": TARGET_ID}, inplace=True)
    df[TARGET_ID] = df[TARGET_ID].map(lambda s: s[len("CHEBI:")])
    df.dropna(inplace=True)

    df[SOURCE_PREFIX] = "ncit"
    df[TARGET_PREFIX] = "chebi"
    df[PROVENANCE] = CHEBI_MAPPINGS_URL
    df = df[XREF_COLUMNS]
    return df


def get_ncit_uniprot_df() -> pd.DataFrame:
    """Get NCIT-UniProt mappings.

    In this file, the only association type was mapsTo.
    """
    df = ensure_df(PREFIX, url=UNIPROT_MAPPINGS_URL, name="ncit_uniprot.csv")
    df.rename(columns={"NCIt Code": SOURCE_ID, "SwissProt ID": TARGET_ID}, inplace=True)
    df[SOURCE_PREFIX] = "ncit"
    df[TARGET_PREFIX] = "uniprot"
    df[PROVENANCE] = UNIPROT_MAPPINGS_URL
    df = df[XREF_COLUMNS]
    return df
