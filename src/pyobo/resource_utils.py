# -*- coding: utf-8 -*-

"""Resource utilities for PyOBO."""

import os
from urllib.request import urlretrieve

from .constants import INSPECTOR_JAVERT_URL, OOH_NA_NA_URL, PYOBO_HOME, REMOTE_ALT_DATA_URL

__all__ = [
    'ensure_inspector_javert',
    'ensure_ooh_na_na',
    'ensure_alts',
]


def ensure_ooh_na_na() -> str:
    """Ensure that the Ooh Na Na Nomenclature Database is downloaded/built."""
    path = os.path.join(PYOBO_HOME, 'ooh_na_na.tsv.gz')
    if not os.path.exists(path):
        urlretrieve(OOH_NA_NA_URL, path)
    return path


def ensure_inspector_javert() -> str:
    """Ensure that the Inspector Javert's Xref Database is downloaded/built."""
    path = os.path.join(PYOBO_HOME, 'inspector_javerts_xrefs.tsv.gz')
    if not os.path.exists(path):
        urlretrieve(INSPECTOR_JAVERT_URL, path)
    return path


def ensure_alts() -> str:
    """Ensure that the alt data is downloaded/built."""
    path = os.path.join(PYOBO_HOME, 'pyobo_alts.tsv.gz')
    if not os.path.exists(path):
        urlretrieve(REMOTE_ALT_DATA_URL, path)
    return path
