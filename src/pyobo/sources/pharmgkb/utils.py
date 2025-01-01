"""Utilities for PharmGKB."""

import pandas as pd
from pystow.utils import read_zipfile_csv

from pyobo.utils.path import ensure_path

__all__ = [
    "download_pharmgkb_tsv",
]

AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/39.0.2171.95 Safari/537.36"


def download_pharmgkb_tsv(prefix: str, url: str, inner: str, *, force: bool) -> pd.DataFrame:
    """Download PharmGKB data."""
    path = ensure_path(
        prefix,
        url=url,
        backend="requests",
        download_kwargs={
            "headers": {
                "User-Agent": AGENT,
            }
        },
        force=force,
    )
    df = read_zipfile_csv(path, inner_path=inner)
    return df
