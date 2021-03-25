# -*- coding: utf-8 -*-

"""Load the manually curated metaregistry."""

import itertools as itt
import json
import os
from functools import lru_cache
from typing import List, Mapping, Set, Tuple

import bioregistry

from ..constants import GLOBAL_SKIP, RAW_DIRECTORY

HERE = os.path.abspath(os.path.dirname(__file__))
CURATED_REGISTRY_PATH = os.path.join(HERE, 'metaregistry.json')


@lru_cache()
def _get_curated_registry():
    """Get the metaregistry."""
    with open(CURATED_REGISTRY_PATH) as file:
        return json.load(file)


@lru_cache(maxsize=1)
def get_wikidata_property_types() -> List[str]:
    """Get the wikidata property types."""
    return _get_curated_registry()['wikidata_property_types']


def not_available_as_obo(prefix: str) -> bool:
    """Return if the prefix is not available."""
    prefix_norm = bioregistry.normalize_prefix(prefix)
    return prefix_norm is not None and prefix_norm in get_not_available_as_obo()


@lru_cache(maxsize=1)
def get_not_available_as_obo():
    """Get the list of prefixes not available as OBO."""
    #: A list of prefixes that have been manually annotated as not being available in OBO
    return {
        bioregistry_prefix
        for bioregistry_prefix, bioregistry_entry in bioregistry.read_bioregistry().items()
        if 'not_available_as_obo' in bioregistry_entry and bioregistry_entry['not_available_as_obo']
    }


@lru_cache(maxsize=1)
def get_curated_urls() -> Mapping[str, str]:
    """Get a mapping of prefixes to their custom download URLs."""
    #: URLs of resources that weren't listed in OBO Foundry properly
    return {
        bioregistry_prefix: bioregistry_entry['download']
        for bioregistry_prefix, bioregistry_entry in bioregistry.read_bioregistry().items()
        if 'download' in bioregistry_entry
    }


@lru_cache(maxsize=1)
def get_xrefs_prefix_blacklist() -> Set[str]:
    """Get the set of blacklisted xref prefixes."""
    #: Xrefs starting with these prefixes will be ignored
    return (
        set(itt.chain.from_iterable(_get_curated_registry()['blacklists']['resource_prefix'].values()))
        | set(_get_curated_registry()['blacklists']['prefix'])
    )


@lru_cache(maxsize=1)
def get_xrefs_suffix_blacklist() -> Set[str]:
    """Get the set of blacklisted xref suffixes."""
    #: Xrefs ending with these suffixes will be ignored
    return set(_get_curated_registry()['blacklists']['suffix'])


@lru_cache(maxsize=1)
def get_xrefs_blacklist() -> Set[str]:
    """Get the set of blacklisted xrefs."""
    rv = set()
    for x in _get_curated_registry()['blacklists']['full']:
        if isinstance(x, str):
            rv.add(x)
        elif isinstance(x, dict):
            if x.get('type') == 'group':
                rv.update(x['text'])
            elif 'text' in x:
                rv.add(x['text'])
            else:
                raise ValueError('invalid schema')
        else:
            raise TypeError
    return rv


@lru_cache(maxsize=1)
def get_remappings_full() -> Mapping[str, str]:
    """Get the remappings for xrefs based on the entire xref database."""
    return _get_curated_registry()['remappings']['full']


def remap_full(x: str) -> str:
    """Remap the string if possible otherwise return it."""
    return get_remappings_full().get(x, x)


@lru_cache(maxsize=1)
def get_remappings_prefix() -> Mapping[str, str]:
    """Get the remappings for xrefs based on the prefix.

    .. note:: Doesn't take into account the semicolon `:`
    """
    return _get_curated_registry()['remappings']['prefix']


@lru_cache(maxsize=1)
def get_prefix_to_miriam_prefix() -> Mapping[str, Tuple[str, str]]:
    """Get a mapping of bioregistry prefixes to MIRIAM prefixes."""
    return {
        prefix: (entry['miriam']['prefix'], entry['miriam']['namespaceEmbeddedInLui'])
        for prefix, entry in bioregistry.read_bioregistry().items()
        if 'miriam' in entry and 'prefix' in entry['miriam']
    }


@lru_cache(maxsize=1)
def get_prefix_to_obofoundry_prefix() -> Mapping[str, str]:
    """Get a mapping of bioregistry prefixes to OBO Foundry prefixes."""
    return _get_map('obofoundry')


@lru_cache(maxsize=1)
def get_prefix_to_ols_prefix() -> Mapping[str, str]:
    """Get a mapping of bioregistry prefixes to OLS prefixes."""
    return _get_map('ols')


def _get_map(registry: str) -> Mapping[str, str]:
    return {
        prefix: entry[registry]['prefix']
        for prefix, entry in bioregistry.read_bioregistry().items()
        if registry in entry
    }


def iter_cached_obo() -> List[Tuple[str, str]]:
    """Iterate over cached OBO paths."""
    for prefix in os.listdir(RAW_DIRECTORY):
        if prefix in GLOBAL_SKIP or not_available_as_obo(prefix) or bioregistry.is_deprecated(prefix):
            continue
        d = os.path.join(RAW_DIRECTORY, prefix)
        if not os.path.isdir(d):
            continue
        for x in os.listdir(d):
            if x.endswith('.obo'):
                p = os.path.join(d, x)
                yield prefix, p
