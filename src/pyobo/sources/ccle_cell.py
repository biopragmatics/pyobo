# -*- coding: utf-8 -*-

"""Get the CCLE Cells, provided by cBioPortal."""

import tarfile
from pathlib import Path
from typing import Iterable, Optional

import pandas as pd
import pystow

from pyobo import Obo, Term

__all__ = [
    'get_obo',
]

PREFIX = 'ccle.cell'


def get_obo(*, version: Optional[str] = None, force: bool = False) -> Obo:
    """Get CCLE Cells as OBO."""
    if version is None:
        version = get_version()
    return Obo(
        ontology=PREFIX,
        name="CCLE Cell Lines",
        iter_terms=iter_terms,
        iter_terms_kwargs=dict(version=version, force=force),
        data_version=version,
        auto_generated_by=f"bio2obo:{PREFIX}",
    )


def iter_terms() -> Iterable[Term]:
    """Iterate over CCLE Cells."""


def get_version() -> str:
    """Get the default version of CCLE's cell lines."""
    return '2019'


def get_url(version: Optional[str] = None) -> str:
    """Get the cBioPortal URL for the given version of CCLE's cell lines."""
    if version is None:
        version = get_version()
    return f'https://cbioportal-datahub.s3.amazonaws.com/ccle_broad_{version}.tar.gz'


def get_inner(version: Optional[str] = None) -> str:
    """Get the inner tarfile path."""
    if version is None:
        version = get_version()
    return f'ccle_broad_{version}/data_clinical_sample.txt'


def ensure(version: Optional[str] = None, **kwargs) -> Path:
    """Ensure the given version is downloaded."""
    if version is None:
        version = get_version()
    url = get_url(version=version)
    return pystow.ensure('pyobo', 'raw', PREFIX, version, url=url, **kwargs)


def ensure_df(version: Optional[str] = None) -> pd.DataFrame:
    """Get the CCLE clinical sample dataframe."""
    if version is None:
        version = get_version()
    path = ensure(version=version)
    inner_path = get_inner(version=version)
    with tarfile.open(path) as tf:
        return pd.read_csv(tf.extractfile(inner_path), sep='\t')


if __name__ == '__main__':
    get_obo().write_default()
