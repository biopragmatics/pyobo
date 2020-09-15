# -*- coding: utf-8 -*-

"""Download registry information from the OBO Foundry."""

import json
import os
import tempfile
from operator import itemgetter
from typing import Optional
from urllib.request import urlretrieve

import click
import yaml

from .utils import list_to_map

__all__ = [
    'OBOFOUNDRY_CACHE_PATH',
    'OBOFOUNDRY_URL',
    'get_obofoundry',
]

HERE = os.path.abspath(os.path.dirname(__file__))

OBOFOUNDRY_CACHE_PATH = os.path.join(HERE, 'obofoundry.json')
OBOFOUNDRY_URL = 'https://raw.githubusercontent.com/OBOFoundry/OBOFoundry.github.io/master/registry/ontologies.yml'


def get_obofoundry(
    cache_path: Optional[str] = OBOFOUNDRY_CACHE_PATH,
    mappify: bool = False,
    force_download: bool = False,
):
    """Get the OBO Foundry registry."""
    if not force_download and cache_path is not None and os.path.exists(cache_path):
        with open(cache_path) as file:
            rv = json.load(file)
            if mappify:
                return list_to_map(rv, 'id')
            return rv

    with tempfile.TemporaryDirectory() as d:
        yaml_path = os.path.join(d, 'obofoundry.yml')
        urlretrieve(OBOFOUNDRY_URL, yaml_path)
        with open(yaml_path) as file:
            rv = yaml.full_load(file)

    rv = rv['ontologies']
    for s in rv:
        for k in ('browsers', 'usages', 'depicted_by', 'products'):
            if k in s:
                del s[k]

    # maintain sorted OBO Foundry
    rv = sorted(rv, key=itemgetter('id'))

    if cache_path is not None:
        with open(cache_path, 'w') as file:
            json.dump(rv, file, indent=2)

    if mappify:
        rv = list_to_map(rv, 'id')

    return rv


@click.command()
def main():
    """Reload the OBO Foundry data."""
    get_obofoundry(force_download=True)


if __name__ == '__main__':
    main()
