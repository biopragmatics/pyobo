# -*- coding: utf-8 -*-

"""Utilities for building paths."""

import logging
from pathlib import Path
from typing import Callable, Optional, Union

import pandas as pd
from pystow.utils import download, name_from_url, read_tarfile_csv

from .misc import cleanup_version
from ..constants import RAW_MODULE

__all__ = [
    "prefix_directory_join",
    "prefix_directory_join",
    "prefix_cache_join",
    "get_prefix_obo_path",
    "ensure_path",
    "ensure_df",
    "ensure_tar_df",
]

logger = logging.getLogger(__name__)

VersionHint = Union[None, str, Callable[[], str]]


def prefix_directory_join(
    prefix: str,
    *parts: str,
    name: Optional[str] = None,
    version: VersionHint = None,
    ensure_exists: bool = True,
) -> Path:
    """Join in the prefix directory."""
    if version is None:
        return RAW_MODULE.join(prefix, *parts, name=name, ensure_exists=ensure_exists)
    if callable(version):
        logger.info("[%s] looking up version", prefix)
        version = version()
        logger.info("[%s] got version %s", prefix, version)
    elif not isinstance(version, str):
        raise TypeError(f"Invalid type: {version} ({type(version)})")
    version = cleanup_version(version, prefix=prefix)
    if version is not None and "/" in version:
        raise ValueError(f"[{prefix}] Can not have slash in version: {version}")
    return RAW_MODULE.join(prefix, version, *parts, name=name, ensure_exists=ensure_exists)


def get_prefix_obo_path(prefix: str, version: VersionHint = None, ext: str = "obo") -> Path:
    """Get the canonical path to the OBO file."""
    return prefix_directory_join(prefix, name=f"{prefix}.{ext}", version=version)


def ensure_path(
    prefix: str,
    *parts: str,
    url: str,
    version: VersionHint = None,
    name: Optional[str] = None,
    force: bool = False,
    error_on_missing: bool = False,
) -> str:
    """Download a file if it doesn't exist."""
    if name is None:
        name = name_from_url(url)

    path = prefix_directory_join(prefix, *parts, name=name, version=version)

    if not path.exists() and error_on_missing:
        raise FileNotFoundError

    download(
        url=url,
        path=path,
        force=force,
    )
    return path.as_posix()


def ensure_df(
    prefix: str,
    *parts: str,
    url: str,
    version: VersionHint = None,
    name: Optional[str] = None,
    force: bool = False,
    sep: str = "\t",
    dtype=str,
    **kwargs,
) -> pd.DataFrame:
    """Download a file and open as a dataframe."""
    _path = ensure_path(prefix, *parts, url=url, version=version, name=name, force=force)
    return pd.read_csv(_path, sep=sep, dtype=dtype, **kwargs)


def ensure_tar_df(
    prefix: str,
    *parts: str,
    url: str,
    inner_path: str,
    version: VersionHint = None,
    path: Optional[str] = None,
    force: bool = False,
    **kwargs,
) -> pd.DataFrame:
    """Download a tar file and open as a dataframe."""
    path = ensure_path(prefix, *parts, url=url, version=version, name=path, force=force)
    return read_tarfile_csv(path, inner_path=inner_path, **kwargs)


def prefix_cache_join(prefix: str, *parts, name: Optional[str], version: VersionHint) -> Path:
    """Ensure the prefix cache is available."""
    return prefix_directory_join(prefix, "cache", *parts, name=name, version=version)
