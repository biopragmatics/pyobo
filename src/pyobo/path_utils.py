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
    'ensure_path',
    'ensure_df',
    'ensure_tar_df',
]

logger = logging.getLogger(__name__)


def get_prefix_directory(prefix: str) -> str:
    """Get the directory."""
    directory = os.path.abspath(os.path.join(PYOBO_HOME, prefix))
    os.makedirs(directory, exist_ok=True)
    return directory


def prefix_directory_join(prefix: str, *parts: str) -> str:
    """Join the parts onto the prefix directory."""
    return os.path.join(get_prefix_directory(prefix), *parts)


def get_prefix_obo_path(prefix: str) -> str:
    """Get the canonical path to the OBO file."""
    return prefix_directory_join(prefix, f"{prefix}.obo")


def ensure_path(prefix: str, url: str, path: Optional[str] = None) -> str:
    """Download a file if it doesn't exist."""
    if path is None:
        parse_result = urlparse(url)
        path = os.path.basename(parse_result.path)

    path = prefix_directory_join(prefix, path)

    if not os.path.exists(path):
        logger.info('downloading %s OBO from %s', prefix, url)
        urlretrieve(url, path)

    return path


def ensure_df(prefix: str, url: str, path: Optional[str] = None, **kwargs) -> pd.DataFrame:
    """Download a file and open as a dataframe."""
    path = ensure_path(prefix, url, path=path)
    return pd.read_csv(path, **kwargs)


def ensure_tar_df(prefix: str, url: str, inner_path: str, **kwargs) -> pd.DataFrame:
    """Download a tar file and open as a dataframe."""
    path = ensure_path(prefix, url)
    with tarfile.open(path) as tar_file:
        with tar_file.extractfile(inner_path) as file:
            return pd.read_csv(file, **kwargs)
