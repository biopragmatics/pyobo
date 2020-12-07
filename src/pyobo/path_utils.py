# -*- coding: utf-8 -*-

"""Utilities for building paths."""

import logging
import os
import tarfile
from pathlib import Path
from typing import Optional
from urllib.request import urlretrieve

import pandas as pd
from pystow.utils import mkdir, name_from_url

from .constants import RAW_MODULE

__all__ = [
    'get_prefix_directory',
    'prefix_directory_join',
    'get_prefix_obo_path',
    'ensure_path',
    'ensure_df',
    'ensure_excel',
    'ensure_tar_df',
]

logger = logging.getLogger(__name__)


def get_prefix_directory(prefix: str, *, version: Optional[str] = None) -> Path:
    """Get the directory."""
    if version is None:
        return RAW_MODULE.get(prefix)
    else:
        return RAW_MODULE.get(prefix, version)


def prefix_directory_join(prefix: str, *parts: str, version: Optional[str] = None) -> Path:
    """Join the parts onto the prefix directory."""
    rv = get_prefix_directory(prefix, version=version).joinpath(*parts)
    mkdir(rv)
    return rv


def get_prefix_obo_path(prefix: str) -> Path:
    """Get the canonical path to the OBO file."""
    return prefix_directory_join(prefix, f"{prefix}.obo")


def ensure_path(
    prefix: str,
    url: str,
    *,
    version: Optional[str] = None,
    path: Optional[str] = None,
    force: bool = False,
) -> str:
    """Download a file if it doesn't exist."""
    if path is None:
        path = name_from_url(url)

    path = prefix_directory_join(prefix, path, version=version)

    if not os.path.exists(path) or force:
        logger.info('[%s] downloading data from %s', prefix, url)
        urlretrieve(url, path)

    return path


def ensure_df(
    prefix: str,
    url: str,
    *,
    version: Optional[str] = None,
    path: Optional[str] = None,
    force: bool = False,
    sep: str = '\t',
    **kwargs,
) -> pd.DataFrame:
    """Download a file and open as a dataframe."""
    path = ensure_path(prefix, url, version=version, path=path, force=force)
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


def prefix_cache_join(prefix: str, *parts):
    """Ensure the prefix cache is available."""
    return prefix_directory_join(prefix, 'cache', *parts)
