# -*- coding: utf-8 -*-

"""Resource utilities for PyOBO."""

import os
from urllib.request import urlretrieve

from .constants import INSPECTOR_JAVERT_URL, OOH_NA_NA_URL, PYOBO_HOME

__all__ = [
    'download_inspector_javert',
    'downlad_ooh_na_na',
]


def downlad_ooh_na_na():
    """Ensure that the Ooh Na Na Nomenclature Database is downloaded/built."""
    path = os.path.join(PYOBO_HOME, 'ooh_na_na.tsv.gz')
    if not os.path.exists(path):
        urlretrieve(OOH_NA_NA_URL, path)


def download_inspector_javert():
    """Ensure that the Inspector Javert's Xref Database is downloaded/built."""
    path = os.path.join(PYOBO_HOME, 'inspector_javerts_xrefs.tsv.gz')
    if not os.path.exists(path):
        urlretrieve(INSPECTOR_JAVERT_URL, path)
