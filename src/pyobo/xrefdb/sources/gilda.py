"""Cross references from Gilda.

.. seealso:: https://github.com/indralabs/gilda
"""

import bioregistry
import pandas as pd

from pyobo.constants import (
    PROVENANCE,
    SOURCE_ID,
    SOURCE_PREFIX,
    TARGET_ID,
    TARGET_PREFIX,
)

__all__ = [
    "get_gilda_xrefs_df",
]

GILDA_MAPPINGS = (
    "https://raw.githubusercontent.com/indralab/gilda/master/gilda/resources/mesh_mappings.tsv"
)


def get_gilda_xrefs_df() -> pd.DataFrame:
    """Get xrefs from Gilda."""
    df = pd.read_csv(
        GILDA_MAPPINGS,
        sep="\t",
        header=None,
        usecols=[0, 1, 3, 4],
        names=[SOURCE_PREFIX, SOURCE_ID, TARGET_PREFIX, TARGET_ID],
    )
    df[PROVENANCE] = GILDA_MAPPINGS

    for k in SOURCE_PREFIX, TARGET_PREFIX:
        df[k] = df[k].map(bioregistry.normalize_prefix)

    for k in SOURCE_ID, TARGET_ID:
        df[k] = df[k].map(_fix_gogo)

    return df


def _fix_gogo(s):
    for prefix in ("CHEBI:", "DOID:", "HP:", "GO:"):
        if s.startswith(prefix):
            return s[len(prefix) :]
    return s
