# -*- coding: utf-8 -*-

import os
from typing import Optional
from urllib.parse import urlparse
from urllib.request import urlretrieve

__all__ = [
    'PYOBO_HOME',
    'OUTPUT_DIRECTORY',
    'get_prefix_directory',
    'ensure_path',
]

PYOBO_HOME = os.environ.get('PYOBO_HOME') or os.path.join(os.path.expanduser('~'), '.obo')

OUTPUT_DIRECTORY = (
    os.environ.get('PYOBO_OUTPUT')
    or os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir, os.pardir, 'obo'))
)


def get_prefix_directory(prefix: str) -> str:
    """Get the directory"""
    directory = os.path.abspath(os.path.join(PYOBO_HOME, prefix))
    os.makedirs(directory, exist_ok=True)
    return directory


def ensure_path(prefix: str, url: str, path: Optional[str] = None) -> str:
    """Download a file if it doesn't exist"""
    if path is None:
        parse_result = urlparse(url)
        path = os.path.basename(parse_result.path)

    directory = get_prefix_directory(prefix)
    path = os.path.join(directory, path)

    if not os.path.exists(path):
        urlretrieve(url, path)

    return path
