"""Constants for miRBase."""

import pandas as pd

from pyobo.utils.path import ensure_df

PREFIX = "mirbase"
BASE_URL = "https://github.com/cthoyt/mirbase/raw/main/"
FROZEN_VERSION = "22.1"


def _assert_frozen_version(version: str):
    if version != FROZEN_VERSION:
        raise ValueError


def get_premature_family_df(version: str, force: bool = False) -> pd.DataFrame:
    """Get premature family dataframe."""
    _assert_frozen_version(version)
    url = f"{BASE_URL}/mirna_prefam.txt.gz"
    return ensure_df(
        PREFIX,
        url=url,
        version=version,
        names=["prefamily_key", "family_id", "family_name"],
        usecols=[0, 1, 2],
        dtype=str,
        force=force,
    )


def get_premature_to_prefamily_df(version: str, force: bool = False) -> pd.DataFrame:
    """Get premature miRNA to premature family dataframe."""
    _assert_frozen_version(version)
    url = f"{BASE_URL}/mirna_2_prefam.txt.gz"
    return ensure_df(
        PREFIX,
        url=url,
        version=version,
        names=["premature_key", "prefamily_key"],
        dtype=str,
        force=force,
    )


def get_premature_df(version: str, force: bool = False) -> pd.DataFrame:
    """Get premature miRNA dataframe."""
    _assert_frozen_version(version)
    url = f"{BASE_URL}/mirna.txt.gz"
    return ensure_df(
        PREFIX,
        url=url,
        version=version,
        names=["premature_key", "mirbase_id", "mirna_name"],
        usecols=[0, 1, 2],
        dtype=str,
        force=force,
    )


def get_mature_df(version: str, force: bool = False) -> pd.DataFrame:
    """Get mature miRNA dataframe."""
    _assert_frozen_version(version)
    url = f"{BASE_URL}/mirna_mature.txt.gz"
    return ensure_df(
        PREFIX,
        url=url,
        version=version,
        names=[
            "mature_key",
            "name",
            "previous",
            "mirbase.mature_id",
        ],
        usecols=[0, 1, 2, 3],
        dtype=str,
        force=force,
    )
