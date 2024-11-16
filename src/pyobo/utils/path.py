"""Utilities for building paths."""

import logging
from pathlib import Path
from typing import Any, Literal

import pandas as pd
import requests_ftp
from pystow import VersionHint

from ..constants import RAW_MODULE

__all__ = [
    "prefix_directory_join",
    "prefix_cache_join",
    "ensure_path",
    "ensure_df",
]

logger = logging.getLogger(__name__)

requests_ftp.monkeypatch_session()


def prefix_directory_join(
    prefix: str,
    *parts: str,
    name: str | None = None,
    version: VersionHint = None,
    ensure_exists: bool = True,
) -> Path:
    """Join in the prefix directory."""
    return RAW_MODULE.module(prefix).join(
        *parts,
        name=name,
        ensure_exists=ensure_exists,
        version=version,
    )


def ensure_path(
    prefix: str,
    *parts: str,
    url: str,
    version: VersionHint = None,
    name: str | None = None,
    force: bool = False,
    backend: Literal["requests", "urllib"] = "urllib",
    verify: bool = True,
    **download_kwargs: Any,
) -> Path:
    """Download a file if it doesn't exist."""
    if verify:
        download_kwargs = {"backend": backend}
    else:
        if backend != "requests":
            logger.warning("using requests since verify=False")
        download_kwargs = {"backend": "requests", "verify": False}

    path = RAW_MODULE.module(prefix).ensure(
        *parts,
        url=url,
        name=name,
        force=force,
        version=version,
        download_kwargs=download_kwargs,
    )
    return path


def ensure_df(
    prefix: str,
    *parts: str,
    url: str,
    version: VersionHint = None,
    name: str | None = None,
    force: bool = False,
    sep: str = "\t",
    dtype=str,
    verify: bool = True,
    backend: Literal["requests", "urllib"] = "urllib",
    **kwargs,
) -> pd.DataFrame:
    """Download a file and open as a dataframe."""
    _path = ensure_path(
        prefix,
        *parts,
        url=url,
        version=version,
        name=name,
        force=force,
        verify=verify,
        backend=backend,
    )
    return pd.read_csv(_path, sep=sep, dtype=dtype, **kwargs)


def prefix_cache_join(prefix: str, *parts, name: str | None, version: VersionHint) -> Path:
    """Ensure the prefix cache is available."""
    return prefix_directory_join(prefix, "cache", *parts, name=name, version=version)
