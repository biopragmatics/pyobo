# -*- coding: utf-8 -*-

"""Utilities for building paths."""

import logging
import os
import tarfile
from pathlib import Path
from typing import Callable, Optional, Union
from urllib.request import urlretrieve

import pandas as pd
from pystow.utils import mkdir, name_from_url

from .constants import RAW_MODULE

__all__ = [
    'get_prefix_directory',
    'prefix_directory_join',
    'prefix_cache_join',
    'get_prefix_obo_path',
    'ensure_path',
    'ensure_df',
    'ensure_excel',
    'ensure_tar_df',
]

logger = logging.getLogger(__name__)

VersionHint = Union[None, str, Callable[[], str]]


def get_prefix_directory(prefix: str, *, version: VersionHint = None) -> Path:
    """Get the directory."""
    if version is None:
        return RAW_MODULE.get(prefix)
    if callable(version):
        logger.info('[%s] looking up version', prefix)
        version = version()
        logger.info('[%s] got version %s', version)
    elif not isinstance(version, str):
        raise TypeError(f'Invalid type: {version} ({type(version)})')
    return RAW_MODULE.get(prefix, version)


def prefix_directory_join(prefix: str, *parts: str, version: VersionHint = None) -> Path:
    """Join the parts onto the prefix directory."""
    rv = get_prefix_directory(prefix, version=version).joinpath(*parts)
    mkdir(rv)
    return rv


def get_prefix_obo_path(prefix: str, version: VersionHint = None) -> Path:
    """Get the canonical path to the OBO file."""
    return prefix_directory_join(prefix, f"{prefix}.obo", version=version)


def ensure_path(
    prefix: str,
    url: str,
    *,
    version: VersionHint = None,
    path: Optional[str] = None,
    force: bool = False,
) -> str:
    """Download a file if it doesn't exist."""
    if path is None:
        path = name_from_url(url)

    path = prefix_directory_join(prefix, path, version=version)

    if not os.path.exists(path) or force:
        logger.info('[%s] downloading data from %s to %s', prefix, url, path)
        urlretrieve(url, path)

    return path.as_posix()


def ensure_df(
    prefix: str,
    url: str,
    *,
    version: VersionHint = None,
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
    version: VersionHint = None,
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
    version: VersionHint,
    path: Optional[str] = None,
    **kwargs,
) -> pd.DataFrame:
    """Download a tar file and open as a dataframe."""
    path = ensure_path(prefix, url, version=version, path=path)
    with tarfile.open(path) as tar_file:
        with tar_file.extractfile(inner_path) as file:
            return pd.read_csv(file, **kwargs)


def prefix_cache_join(prefix: str, *parts, version: VersionHint = None):
    """Ensure the prefix cache is available."""
    return prefix_directory_join(prefix, 'cache', *parts, version=version)
