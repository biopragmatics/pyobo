"""Get the CCLE Cells, provided by cBioPortal."""

import tarfile
from collections.abc import Iterable
from pathlib import Path
from typing import Optional

import pandas as pd
import pystow

from pyobo import Obo, Reference, Term

__all__ = [
    "get_obo",
    "CCLEGetter",
]

PREFIX = "ccle"
VERSION = "2019"


class CCLEGetter(Obo):
    """An ontology representation of the Cancer Cell Line Encyclopedia's cell lines."""

    ontology = bioregistry_key = PREFIX

    def __post_init__(self):
        self.data_version = VERSION

    def iter_terms(self, force: bool = False) -> Iterable[Term]:
        """Iterate over terms in the ontology."""
        return iter_terms(version=self._version_or_raise, force=force)


def get_obo(*, force: bool = False) -> Obo:
    """Get CCLE Cells as OBO."""
    return CCLEGetter(force=force)


def iter_terms(version: Optional[str] = None, force: bool = False) -> Iterable[Term]:
    """Iterate over CCLE Cells."""
    df = ensure_df(version=version, force=force)
    for identifier, depmap_id, name in df.values:
        if pd.isna(name) or pd.isnull(name):
            name = None
        term = Term.from_triple(PREFIX, identifier, name)
        if pd.notna(depmap_id):
            term.append_xref(Reference(prefix="depmap", identifier=depmap_id))
        yield term


def get_ccle_static_version() -> str:
    """Get the default version of CCLE's cell lines."""
    return "2019"


def get_url(version: Optional[str] = None) -> str:
    """Get the cBioPortal URL for the given version of CCLE's cell lines."""
    if version is None:
        version = get_ccle_static_version()
    return f"https://cbioportal-datahub.s3.amazonaws.com/ccle_broad_{version}.tar.gz"


def get_inner(version: Optional[str] = None) -> str:
    """Get the inner tarfile path."""
    if version is None:
        version = get_ccle_static_version()
    return f"ccle_broad_{version}/data_clinical_sample.txt"


def ensure(version: Optional[str] = None, **kwargs) -> Path:
    """Ensure the given version is downloaded."""
    if version is None:
        version = get_ccle_static_version()
    url = get_url(version=version)
    return pystow.ensure("pyobo", "raw", PREFIX, version, url=url, **kwargs)


def ensure_df(version: Optional[str] = None, force: bool = False) -> pd.DataFrame:
    """Get the CCLE clinical sample dataframe."""
    if version is None:
        version = get_ccle_static_version()
    path = ensure(version=version, force=force)
    inner_path = get_inner(version=version)
    with tarfile.open(path) as tf:
        return pd.read_csv(
            tf.extractfile(inner_path),
            sep="\t",
            skiprows=4,  # includes skipping header
            dtype=str,
            usecols=[
                0,  # Sample Identifier
                5,  # DepMap ID
                6,  # Name
                # There are lots of other wonderful sample metadata in case we want more later
            ],
        )


if __name__ == "__main__":
    CCLEGetter.cli()
