# -*- coding: utf-8 -*-

"""Load the manually curated metaregistry."""

import json
import os
from functools import lru_cache
from typing import List, Mapping, Set, Tuple

import bioregistry

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
    return set(_get_curated_registry()['blacklists']['prefix'])


@lru_cache(maxsize=1)
def get_xrefs_suffix_blacklist() -> Set[str]:
    """Get the set of blacklisted xref suffixes."""
    #: Xrefs ending with these suffixes will be ignored
    return set(_get_curated_registry()['blacklists']['suffix'])


@lru_cache(maxsize=1)
def get_xrefs_blacklist() -> Set[str]:
    """Get the set of blacklisted xrefs."""
    return set(_get_curated_registry()['blacklists']['full'])


@lru_cache(maxsize=1)
def get_remappings_full() -> Mapping[str, str]:
    """Get the remappings for xrefs based on the entire xref database."""
    return _get_curated_registry()['remappings']['full']


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
