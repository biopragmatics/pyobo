# -*- coding: utf-8 -*-

"""Constants for miRBase."""

import pandas as pd

from pyobo.utils.path import ensure_df

PREFIX = "mirbase"

# PREMATURE_TO_MATURE = f'https://mirbase.org/ftp/{VERSION}/database_files/mirna_pre_mature.txt.gz'


def get_premature_family_df(version: str, force: bool = False) -> pd.DataFrame:
    """Get premature family dataframe."""
    url = f"https://mirbase.org/ftp/{version}/database_files/mirna_prefam.txt.gz"
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
    url = f"https://mirbase.org/ftp/{version}/database_files/mirna_2_prefam.txt.gz"
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
    url = f"https://mirbase.org/ftp/{version}/database_files/mirna.txt.gz"
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
    url = f"https://mirbase.org/ftp/{version}/database_files/mirna_mature.txt.gz"
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
