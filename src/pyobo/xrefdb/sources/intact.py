"""Get the xrefs from IntAct."""

from collections.abc import Mapping

import pandas as pd

from pyobo.api.utils import get_version
from pyobo.constants import PROVENANCE, SOURCE_PREFIX, TARGET_PREFIX, XREF_COLUMNS
from pyobo.utils.cache import cached_mapping
from pyobo.utils.path import prefix_cache_join

__all__ = [
    "COMPLEXPORTAL_MAPPINGS",
    "get_intact_complex_portal_xrefs_df",
    "get_complexportal_mapping",
    "get_intact_reactome_xrefs_df",
    "get_reactome_mapping",
]

COMPLEXPORTAL_MAPPINGS = (
    "ftp://ftp.ebi.ac.uk/pub/databases/intact/current/various/cpx_ebi_ac_translation.txt"
)
REACTOME_MAPPINGS = "ftp://ftp.ebi.ac.uk/pub/databases/intact/current/various/reactome.dat"


def _get_complexportal_df():
    return pd.read_csv(
        COMPLEXPORTAL_MAPPINGS, sep="\t", header=None, names=["source_id", "target_id"]
    )


def get_intact_complex_portal_xrefs_df() -> pd.DataFrame:
    """Get IntAct-Complex Portal xrefs."""
    df = _get_complexportal_df()
    df[SOURCE_PREFIX] = "intact"
    df[TARGET_PREFIX] = "complexportal"
    df[PROVENANCE] = COMPLEXPORTAL_MAPPINGS
    df = df[XREF_COLUMNS]
    return df


def get_complexportal_mapping() -> Mapping[str, str]:
    """Get IntAct to Complex Portal mapping.

    Is basically equivalent to:

    .. code-block:: python

        from pyobo import get_filtered_xrefs

        intact_complexportal_mapping = get_filtered_xrefs("intact", "complexportal")
    """

    @cached_mapping(
        path=prefix_cache_join(
            "intact", "xrefs", name="complexportal.tsv", version=get_version("intact")
        ),
        header=["intact_id", "complexportal_id"],
    )
    def _cache():
        df = _get_complexportal_df()
        return dict(df.values)

    return _cache()


def _get_reactome_df():
    return pd.read_csv(REACTOME_MAPPINGS, sep="\t", header=None, names=["source_id", "target_id"])


def get_intact_reactome_xrefs_df() -> pd.DataFrame:
    """Get IntAct-Reactome xrefs."""
    df = _get_reactome_df()
    df[SOURCE_PREFIX] = "intact"
    df[TARGET_PREFIX] = "reactome"
    df[PROVENANCE] = REACTOME_MAPPINGS
    df = df[XREF_COLUMNS]
    return df


def get_reactome_mapping() -> Mapping[str, str]:
    """Get IntAct to Reactome mapping.

    Is basically equivalent to:

    .. code-block:: python

        from pyobo import get_filtered_xrefs

        intact_complexportal_mapping = get_filtered_xrefs("intact", "reactome")
    """

    @cached_mapping(
        path=prefix_cache_join(
            "intact", "xrefs", name="reactome.tsv", version=get_version("intact")
        ),
        header=["intact_id", "reactome_id"],
    )
    def _cache():
        df = _get_complexportal_df()
        return dict(df.values)

    return _cache()


def get_xrefs_df() -> pd.DataFrame:
    """Get IntAct xrefs."""
    return pd.concat(
        [
            get_intact_complex_portal_xrefs_df(),
            get_intact_reactome_xrefs_df(),
        ]
    )
