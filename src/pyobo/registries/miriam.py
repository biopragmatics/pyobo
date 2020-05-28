# -*- coding: utf-8 -*-

"""Download registry information from Identifiers.org/MIRIAMs."""

import os
from typing import Optional

import click

from .utils import ensure_registry

__all__ = [
    'MIRIAM_CACHE_PATH',
    'MIRIAM_URL',
    'get_miriam',
]

HERE = os.path.abspath(os.path.dirname(__file__))

MIRIAM_CACHE_PATH = os.path.join(HERE, 'miriam.json')
MIRIAM_URL = 'https://registry.api.identifiers.org/restApi/namespaces'


def get_miriam(cache_path: Optional[str] = MIRIAM_CACHE_PATH, mappify: bool = False, force_download: bool = False):
    """Get the MIRIAM registry."""
    return ensure_registry(
        url=MIRIAM_URL,
        embedded_key='namespaces',
        cache_path=cache_path,
        id_key='prefix',
        mappify=mappify,
        force_download=force_download,
    )


@click.command()
def main():
    """Reload the MIRIAM data."""
    get_miriam(force_download=True)


if __name__ == '__main__':
    main()
