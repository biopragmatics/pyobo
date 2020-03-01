# -*- coding: utf-8 -*-

"""Download information from several registries."""

import json
import os
import tempfile
from pprint import pprint
from typing import Optional
from urllib.request import urlretrieve

import requests
import yaml

__all__ = [
    'download_obofoundry',
    'download_miriam',
    'download_ols',
]

HERE = os.path.abspath(os.path.dirname(__file__))

OBOFOUNDRY_URL = 'https://raw.githubusercontent.com/OBOFoundry/OBOFoundry.github.io/master/registry/ontologies.yml'
MIRIAM_URL = 'https://registry.api.identifiers.org/restApi/namespaces'
OLS_URL = 'http://www.ebi.ac.uk/ols/api/ontologies'

OBOFOUNDRY_CACHE_PATH = os.path.join(HERE, 'obofoundry.json')
MIRIAM_CACHE_PATH = os.path.join(HERE, 'miriam.json')
OLS_CACHE_PATH = os.path.join(HERE, 'ols.json')


def download_obofoundry(cache_path: Optional[str] = OBOFOUNDRY_CACHE_PATH):
    if cache_path is not None and os.path.exists(cache_path):
        with open(cache_path) as file:
            return json.load(file)

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

    if cache_path is not None:
        with open(cache_path, 'w') as file:
            json.dump(rv, file, indent=2)

    return rv


def download_miriam(cache_path: Optional[str] = MIRIAM_CACHE_PATH):
    return _ensure(MIRIAM_URL, embedded_key='namespaces', cache_path=cache_path)


def download_ols(cache_path: Optional[str] = OLS_CACHE_PATH):
    return _ensure(OLS_URL, embedded_key='ontologies', cache_path=cache_path)


def _ensure(url, embedded_key, cache_path: Optional[str] = None):
    if cache_path is not None and os.path.exists(cache_path):
        with open(cache_path) as file:
            return json.load(file)

    results = _download_paginated(url, embedded_key=embedded_key)
    if cache_path is not None:
        with open(cache_path, 'w') as file:
            json.dump(results, file, indent=2)
    return results


def _download_paginated(start_url, embedded_key):
    results = []
    url = start_url
    while True:
        print('getting', url)
        g = requests.get(url)
        j = g.json()
        r = j['_embedded'][embedded_key]
        pprint(r)
        results.extend(r)
        links = j['_links']
        if 'next' not in links:
            break
        url = links['next']['href']
    return results
