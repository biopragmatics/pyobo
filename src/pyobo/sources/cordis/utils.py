"""Utilities for CORDIS resources."""

from __future__ import annotations

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
    "TOPIC_PREFIX",
    "URL",
    "clean_topic_id",
    "get_cordis_path",
    "open_cordis",
]

#: A URL for the latest CORDIS data dump
URL = "https://cordis.europa.eu/data/cordis-h2020projects-csv.zip"

PROJECT_PREFIX = "cordis.project"
ORGANIZATION_PREFIX = "cordis.organization"
BASIS_PREFIX = "cordis.basis"
TOPIC_PREFIX = "cordis.topic"


def get_cordis_path(*, version: str | None = None) -> Path:
    """Get the CORDIS data dump."""
    return ensure_path("cordis", url=URL, version=version)


@contextmanager
def open_cordis(
    inner_path: str, *, version: str | None = None
) -> Generator[csv.DictReader[str], None, None]:
    """Open a CORDIS CSV."""
    path = get_cordis_path(version=version)
    with open_zip_dict_reader(path, inner_path, delimiter=";", quoting=csv.QUOTE_MINIMAL) as reader:
        yield reader


def clean_topic_id(topic_id: str) -> str:
    """Fix CORDIS topic IDs that might have spaces in them."""
    # identifier cleanup needed for `RISK FINANCE` and `SCIENCE WAF SOCIETY`
    return topic_id.replace(" ", "%20")
