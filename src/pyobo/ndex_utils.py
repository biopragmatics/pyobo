# -*- coding: utf-8 -*-

"""Utilities for caching files from NDEx."""

import json
import os
from typing import Any, Iterable, List, Mapping, Tuple

import requests
from tqdm import tqdm

from .path_utils import prefix_directory_join

__all__ = [
    'CX',
    'ensure_ndex_network',
    'ensure_ndex_network_set',
    'iterate_aspect',
]

NDEX_BASE_URL = 'http://public.ndexbio.org/v2'
NETWORK_ENDPOINT = f'{NDEX_BASE_URL}/network'
NETWORKSET_ENDPOINT = f'{NDEX_BASE_URL}/networkset'
CX = List[Mapping[str, Any]]


def iterate_aspect(cx: CX, aspect: str) -> List[Any]:
    """Iterate over a given aspect."""
    for element in cx:
        if aspect in element:
            yield from element[aspect]


def ensure_ndex_network(prefix: str, uuid: str) -> CX:
    """Ensure a network from NDEx is cached."""
    path = prefix_directory_join(prefix, 'ndex', f'{uuid}.json')
    if os.path.exists(path):
        with open(path) as file:
            return json.load(file)

    res = requests.get(f'{NETWORK_ENDPOINT}/{uuid}')
    res_json = res.json()
    with open(path, 'w') as file:
        json.dump(res_json, file, indent=2)
    return res_json


def ensure_ndex_network_set(prefix: str, uuid: str, use_tqdm: bool = False) -> Iterable[Tuple[str, CX]]:
    """Ensure the list of networks that goes with NCI PID on NDEx."""
    it = _help_ensure_ndex_network_set(prefix, uuid)
    if use_tqdm:
        it = tqdm(it, desc=f'ensuring networks from {uuid}')
    for network_uuid in it:
        yield network_uuid, ensure_ndex_network(prefix, network_uuid)


def _help_ensure_ndex_network_set(prefix: str, uuid: str) -> List[str]:
    """Ensure the list of networks that goes with NCI PID on NDEx."""
    networkset_path = prefix_directory_join(prefix, 'networks.txt')
    if os.path.exists(networkset_path):
        with open(networkset_path) as file:
            return sorted(line.strip() for line in file)

    url = f'{NETWORKSET_ENDPOINT}/{uuid}'
    res = requests.get(url)
    res_json = res.json()
    network_uuids = res_json['networks']
    with open(networkset_path, 'w') as file:
        for network_uuid in sorted(network_uuids):
            print(network_uuid, file=file)
    return network_uuids
