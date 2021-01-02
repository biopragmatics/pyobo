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
from pystow.utils import mkdir, name_from_url

from .constants import RAW_MODULE

__all__ = [
    'get_prefix_directory',
    'prefix_directory_join',
    'prefix_cache_join',
    'get_prefix_obo_path',
    'ensure_path',
    'ensure_df',
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
        logger.info('downloading from %s to %s', url, path)
        urlretrieve(url, path)  # noqa:S310
    else:
        # see https://requests.readthedocs.io/en/master/user/quickstart/#raw-response-content
        # pattern from https://stackoverflow.com/a/39217788/5775947
        try:
            with requests.get(url, stream=True, **kwargs) as response, open(path, 'wb') as file:
                logger.info('downloading (streaming) from %s to %s', url, path)
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
    path: Optional[str] = None,
    force: bool = False,
    stream: bool = False,
    urlretrieve_kwargs: Optional[Mapping[str, Any]] = None,
    error_on_missing: bool = False,
) -> str:
    """Download a file if it doesn't exist."""
    if path is None:
        path = name_from_url(url)

    _path = prefix_directory_join(prefix, *parts, path, version=version)

    if not _path.exists() and error_on_missing:
        raise FileNotFoundError

    if not _path.exists() or force:
        _urlretrieve(url=url, path=_path, stream=stream, **(urlretrieve_kwargs or {}))

    return _path.as_posix()


def ensure_df(
    prefix: str,
    *parts: str,
    url: str,
    version: VersionHint = None,
    path: Optional[str] = None,
    force: bool = False,
    sep: str = '\t',
    dtype=str,
    **kwargs,
) -> pd.DataFrame:
    """Download a file and open as a dataframe."""
    path = ensure_path(prefix, *parts, url=url, version=version, path=path, force=force)
    return pd.read_csv(path, sep=sep, dtype=dtype, **kwargs)


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
    path = ensure_path(prefix, *parts, url=url, version=version, path=path)
    with tarfile.open(path) as tar_file:
        with tar_file.extractfile(inner_path) as file:
            return pd.read_csv(file, **kwargs)


def prefix_cache_join(prefix: str, *parts, version: VersionHint = None):
    """Ensure the prefix cache is available."""
    return prefix_directory_join(prefix, 'cache', *parts, version=version)
