"""Get the Biomappings manually curated equivalences."""

import pandas as pd
from pystow.utils import get_commit

from pyobo.constants import (
    PROVENANCE,
    SOURCE_ID,
    SOURCE_PREFIX,
    TARGET_ID,
    TARGET_PREFIX,
    XREF_COLUMNS,
)

__all__ = [
    "get_biomappings_df",
]


def get_biomappings_df() -> pd.DataFrame:
    """Get biomappings equivalences."""
    sha = get_commit("biopragmatics", "biomappings")
    url = f"https://raw.githubusercontent.com/biopragmatics/biomappings/{sha}/src/biomappings/resources/mappings.tsv"
    df = pd.read_csv(url, sep="\t")
    df[PROVENANCE] = url
    df.rename(
        columns={
            "source prefix": SOURCE_PREFIX,
            "source identifier": SOURCE_ID,
            "target prefix": TARGET_PREFIX,
            "target identifier": TARGET_ID,
        },
        inplace=True,
    )
    df = df[XREF_COLUMNS]
    return df
