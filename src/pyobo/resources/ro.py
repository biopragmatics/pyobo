# -*- coding: utf-8 -*-

import os
from functools import lru_cache
from typing import Mapping, Tuple

import requests

__all__ = [
    'load_ro',
]

HERE = os.path.abspath(os.path.dirname(__file__))
PATH = os.path.join(HERE, 'ro.tsv')
URL = 'http://purl.obolibrary.org/obo/ro.json'
PREFIX = 'http://purl.obolibrary.org/obo/'


@lru_cache(maxsize=1)
def load_ro() -> Mapping[Tuple[str, str], str]:
    """Load the relation ontology names."""
    rv = {}
    with open(PATH) as file:
        for line in file:
            prefix, identifier, name = line.strip().split('\t')
            rv[prefix, identifier] = name
    return rv


def download():
    """Download the latest version of the Relation Ontology."""
    rows = []
    res_json = requests.get(URL).json()
    for node in res_json['graphs'][0]['nodes']:
        identifier = node['id']
        if not identifier.startswith(PREFIX):
            continue
        identifier = identifier[len(PREFIX):]
        if all(not identifier.startswith(p) for p in ('RO', 'BFO', 'UPHENO')):
            continue
        prefix, identifier = identifier.split('_', 1)
        name = node.get('lbl')
        if name:
            rows.append((prefix.lower(), identifier, name))

    with open(PATH, 'w') as file:
        for prefix, identifier, name in sorted(rows):
            print(prefix, identifier, name, sep='\t', file=file)


if __name__ == '__main__':
    from pprint import pprint

    download()
    pprint(load_ro())
