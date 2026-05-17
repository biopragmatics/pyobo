"""Utilities for CORDIS resources."""

from pathlib import Path

from pyobo.utils.path import ensure_path

__all__ = ["get_cordis_path"]

URL = "https://cordis.europa.eu/data/cordis-h2020projects-csv.zip"


def get_cordis_path(version: str | None = None) -> Path:
    """Get the CORDIS data dump."""
    return ensure_path("cordis", url=URL, version=version)
