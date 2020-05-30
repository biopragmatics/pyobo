# -*- coding: utf-8 -*-

"""Load the manually curated metaregistry."""

import json
import os
from typing import Mapping, Tuple

__all__ = [
    'CURATED_REGISTRY_PATH',
    'get_curated_registry',
]

HERE = os.path.abspath(os.path.dirname(__file__))

CURATED_REGISTRY_PATH = os.path.join(HERE, 'metaregistry.json')


def get_curated_registry():
    """Get the metaregistry."""
    with open(CURATED_REGISTRY_PATH) as file:
        x = json.load(file)
    with open(CURATED_REGISTRY_PATH, 'w') as file:
        json.dump(x, file, indent=2, sort_keys=True)
    return x


CURATED_REGISTRY = get_curated_registry()

CURATED_REGISTRY_DATABASE = CURATED_REGISTRY['database']

#: A list of prefixes that have been manually annotated as not being available in OBO
NOT_AVAILABLE_AS_OBO = {
    prefix
    for prefix, entry in CURATED_REGISTRY_DATABASE.items()
    if 'not_available_as_obo' in entry and entry['not_available_as_obo']
}

#: URLs of resources that weren't listed in OBO Foundry properly
CURATED_URLS = {
    k: v['download']
    for k, v in CURATED_REGISTRY_DATABASE.items()
    if 'download' in v
}

#: Xrefs starting with these prefixes will be ignored
XREF_PREFIX_BLACKLIST = set(CURATED_REGISTRY['blacklists']['prefix'])
#: Xrefs ending with these suffixes will be ignored
XREF_SUFFIX_BLACKLIST = set(CURATED_REGISTRY['blacklists']['suffix'])
#: Xrefs matching these will be ignored
XREF_BLACKLIST = set(CURATED_REGISTRY['blacklists']['full'])

#: A list of prefixes that have been manually annotated as obsolete
OBSOLETE = CURATED_REGISTRY['obsolete']

#: Remappings for xrefs based on the entire xre
REMAPPINGS_FULL = CURATED_REGISTRY['remappings']['full']
#: Remappings for xrefs based on the prefix. Doesn't take into account the semicolon :
REMAPPINGS_PREFIX = CURATED_REGISTRY['remappings']['prefix']

PREFIX_TO_MIRIAM_PREFIX: Mapping[str, Tuple[str, str]] = {
    prefix: (entry['miriam']['prefix'], entry['miriam']['namespaceEmbeddedInLui'])
    for prefix, entry in CURATED_REGISTRY_DATABASE.items()
    if 'miriam' in entry
}
