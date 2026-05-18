"""Utilities for CORDIS resources."""

import csv
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path

from pystow.utils import open_zip_dict_reader

from pyobo.utils.path import ensure_path

__all__ = [
    "BASIS_PREFIX",
    "ORGANIZATION_PREFIX",
    "PROJECT_PREFIX",
    "URL",
    "get_cordis_path",
    "open_cordis",
]

#: A URL for the latest CORDIS data dump
URL = "https://cordis.europa.eu/data/cordis-h2020projects-csv.zip"

PROJECT_PREFIX = "cordis.project"
ORGANIZATION_PREFIX = "cordis.organization"
BASIS_PREFIX = "cordis.basis"


def get_cordis_path(*, version: str | None = None) -> Path:
    """Get the CORDIS data dump."""
    return ensure_path("cordis", url=URL, version=version)


@contextmanager
def open_cordis(
    inner_path: str, *, version: str | None = None
) -> Generator[csv.DictReader[str], None, None]:
    """Open a CORDIS CSV."""
    path = get_cordis_path(version=version)
    with open_zip_dict_reader(path, inner_path, delimiter=";") as reader:
        yield reader
