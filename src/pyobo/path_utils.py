# -*- coding: utf-8 -*-

"""Utilities for building paths."""

import logging
import os
import tarfile
from typing import Optional
from urllib.parse import urlparse
from urllib.request import urlretrieve

import pandas as pd

from .constants import PYOBO_HOME

__all__ = [
    'get_prefix_directory',
    'prefix_directory_join',
    'get_prefix_obo_path',
    'get_url_filename',
    'ensure_path',
    'ensure_df',
    'ensure_excel',
    'ensure_tar_df',
]

logger = logging.getLogger(__name__)


def get_prefix_directory(prefix: str, *, version: Optional[str] = None) -> str:
    """Get the directory."""
    if version:
        directory = os.path.abspath(os.path.join(PYOBO_HOME, prefix, version))
    else:
        directory = os.path.abspath(os.path.join(PYOBO_HOME, prefix))
    os.makedirs(directory, exist_ok=True)
    return directory


def prefix_directory_join(prefix: str, *parts: str, version: Optional[str] = None) -> str:
    """Join the parts onto the prefix directory."""
    rv = os.path.join(get_prefix_directory(prefix, version=version), *parts)
    os.makedirs(os.path.dirname(rv), exist_ok=True)
    return rv


def get_prefix_obo_path(prefix: str) -> str:
    """Get the canonical path to the OBO file."""
    return prefix_directory_join(prefix, f"{prefix}.obo")


def get_url_filename(url: str) -> str:
    """Get the filename from the end of the URL."""
    parse_result = urlparse(url)
    return os.path.basename(parse_result.path)


def ensure_path(
    prefix: str,
    url: str,
    *,
    version: Optional[str] = None,
    path: Optional[str] = None,
) -> str:
    """Download a file if it doesn't exist."""
    if path is None:
        path = get_url_filename(url)

    if version:
        path = prefix_directory_join(prefix, path, version=version)
    else:
        path = prefix_directory_join(prefix, path)

    if not os.path.exists(path):
        logger.info('downloading %s OBO from %s', prefix, url)
        urlretrieve(url, path)

    return path


def ensure_df(
    prefix: str,
    url: str,
    *,
    version: Optional[str] = None,
    path: Optional[str] = None,
    sep: str = '\t',
    **kwargs,
) -> pd.DataFrame:
    """Download a file and open as a dataframe."""
    path = ensure_path(prefix, url, version=version, path=path)
    return pd.read_csv(path, sep=sep, **kwargs)


def ensure_excel(
    prefix: str,
    url: str,
    *,
    version: Optional[str] = None,
    path: Optional[str] = None,
    **kwargs,
) -> pd.DataFrame:
    """Download an excel file and open as a dataframe."""
    path = ensure_path(prefix, url, version=version, path=path)
    return pd.read_excel(path, **kwargs)


def ensure_tar_df(
    prefix: str,
    url: str,
    inner_path: str,
    *,
    version: Optional[str] = None,
    path: Optional[str] = None,
    **kwargs,
) -> pd.DataFrame:
    """Download a tar file and open as a dataframe."""
    path = ensure_path(prefix, url, version=version, path=path)
    with tarfile.open(path) as tar_file:
        with tar_file.extractfile(inner_path) as file:
            return pd.read_csv(file, **kwargs)
