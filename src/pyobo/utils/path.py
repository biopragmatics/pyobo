# -*- coding: utf-8 -*-

"""Utilities for building paths."""

import logging
import os
import shutil
import tarfile
from pathlib import Path
from typing import Any, Callable, Mapping, Optional, Union
from urllib.request import urlretrieve

import pandas as pd
import requests
from pystow.utils import name_from_url

from pyobo.constants import RAW_MODULE

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
        logger.info("[%s] got version %s", version)
    elif not isinstance(version, str):
        raise TypeError(f"Invalid type: {version} ({type(version)})")
    return RAW_MODULE.join(prefix, version, *parts, name=name, ensure_exists=ensure_exists)


def get_prefix_obo_path(prefix: str, version: VersionHint = None, ext: str = "obo") -> Path:
    """Get the canonical path to the OBO file."""
    return prefix_directory_join(prefix, name=f"{prefix}.{ext}", version=version)


# TODO replace with pystow.download
def _urlretrieve(
    url: str,
    path: Union[str, Path],
    clean_on_failure: bool = True,
    stream: bool = True,
    **kwargs,
) -> None:
    """Download a file from a given URL.

    :param url: URL to download
    :param path: Path to download the file to
    :param clean_on_failure: If true, will delete the file on any exception raised during download
    """
    if not stream:
        logger.info("downloading from %s to %s", url, path)
        urlretrieve(url, path)  # noqa:S310
    else:
        # see https://requests.readthedocs.io/en/master/user/quickstart/#raw-response-content
        # pattern from https://stackoverflow.com/a/39217788/5775947
        try:
            with requests.get(url, stream=True, **kwargs) as response, open(path, "wb") as file:
                logger.info("downloading (streaming) from %s to %s", url, path)
                shutil.copyfileobj(response.raw, file)
        except (Exception, KeyboardInterrupt):
            if clean_on_failure:
                os.remove(path)
            raise


def ensure_path(
    prefix: str,
    *parts: str,
    url: str,
    version: VersionHint = None,
    name: Optional[str] = None,
    force: bool = False,
    stream: bool = False,
    urlretrieve_kwargs: Optional[Mapping[str, Any]] = None,
    error_on_missing: bool = False,
) -> str:
    """Download a file if it doesn't exist."""
    if name is None:
        name = name_from_url(url)

    path = prefix_directory_join(prefix, *parts, name=name, version=version)

    if not path.exists() and error_on_missing:
        raise FileNotFoundError

    if not path.exists() or force:
        _urlretrieve(url=url, path=path, stream=stream, **(urlretrieve_kwargs or {}))

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
    **kwargs,
) -> pd.DataFrame:
    """Download a tar file and open as a dataframe."""
    path = ensure_path(prefix, *parts, url=url, version=version, name=path)
    with tarfile.open(path) as tar_file:
        with tar_file.extractfile(inner_path) as file:
            return pd.read_csv(file, **kwargs)


def prefix_cache_join(prefix: str, *parts, name: Optional[str], version: VersionHint) -> Path:
    """Ensure the prefix cache is available."""
    return prefix_directory_join(prefix, "cache", *parts, name=name, version=version)
