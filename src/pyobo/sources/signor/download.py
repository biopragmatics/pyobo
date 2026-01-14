"""Download utilities for SIGNOR."""

import enum

import pandas as pd
import requests

from pyobo.utils.path import prefix_directory_join

__all__ = [
    "DownloadKey",
    "download_signor",
    "get_signor_df",
]


class DownloadKey(enum.Enum):
    """Download key."""

    complex = "Download complex data"
    family = "Download protein family data"
    phenotype = "Download phenotype data"
    stimulus = "Download stimulus data"


def download_signor(key: DownloadKey) -> requests.Response:
    """Download from SIGNOR."""
    return requests.post(
        "https://signor.uniroma2.it/download_complexes.php",
        files={"submit": (None, key.value)},
    )


def get_signor_df(prefix: str, *, version: str, key: DownloadKey, force: bool) -> pd.DataFrame:
    """Get the appropriate SIGNOR dataframe."""
    path = prefix_directory_join(prefix, version=version, name=f"{key.name}.csv")
    if not path.is_file() or force:
        res = download_signor(key)
        path.write_text(res.text)
    df = pd.read_csv(path, sep=";")
    return df
