# -*- coding: utf-8 -*-

"""Resource utilities for PyOBO."""

import os
from typing import Optional
from urllib.request import urlretrieve

import pandas as pd

from .constants import DATABASE_DIRECTORY, INSPECTOR_JAVERT_URL, OOH_NA_NA_URL, REMOTE_ALT_DATA_URL, SYNONYMS_URL

__all__ = [
    'ensure_inspector_javert',
    'ensure_ooh_na_na',
    'ensure_alts',
    'ensure_synonyms',
]


def ensure_ooh_na_na(force: bool = False) -> str:
    """Ensure that the Ooh Na Na Nomenclature Database is downloaded/built."""
    return _ensure(url=OOH_NA_NA_URL, name='names.tsv.gz', force=force)


def get_ooh_na_na(force: bool = False, chunksize: Optional[int] = None) -> pd.DataFrame:
    """Get the Ooh Na Na database.

    If chunksize is given, will read in chunks and return an iterator instead of a dataframe.
    """
    path = ensure_ooh_na_na(force=force)
    return pd.read_csv(path, sep='\t', chunksize=chunksize, dtype=str)


def ensure_inspector_javert(force: bool = False) -> str:
    """Ensure that the Inspector Javert's Xref Database is downloaded/built."""
    return _ensure(url=INSPECTOR_JAVERT_URL, name='xrefs.tsv.gz', force=force)


def ensure_synonyms(force: bool = False) -> str:
    """Ensure that the Synonym Database is downloaded/built."""
    return _ensure(url=SYNONYMS_URL, name='synonyms.tsv.gz', force=force)


def ensure_alts(force: bool = False) -> str:
    """Ensure that the alt data is downloaded/built."""
    return _ensure(url=REMOTE_ALT_DATA_URL, name='alts.tsv.gz', force=force)


def _ensure(url: str, name: str, force: bool = False) -> str:
    path = os.path.join(DATABASE_DIRECTORY, name)
    if not os.path.exists(path) or force:
        urlretrieve(url, path)
    return path
