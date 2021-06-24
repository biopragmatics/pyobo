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
CURATED_REGISTRY_PATH = os.path.join(HERE, "metaregistry.json")


@lru_cache()
def _get_curated_registry():
    """Get the metaregistry."""
    with open(CURATED_REGISTRY_PATH) as file:
        return json.load(file)


@lru_cache(maxsize=1)
def get_wikidata_property_types() -> List[str]:
    """Get the wikidata property types."""
    return _get_curated_registry()["wikidata_property_types"]


def has_no_download(prefix: str) -> bool:
    """Return if the prefix is not available."""
    prefix_norm = bioregistry.normalize_prefix(prefix)
    return prefix_norm is not None and prefix_norm in _no_download()


@lru_cache(maxsize=1)
def _no_download() -> Set[str]:
    """Get the list of prefixes not available as OBO."""
    return {
        prefix
        for prefix in bioregistry.read_registry()
        if bioregistry.get_obo_download(prefix) is None
        and bioregistry.get_owl_download(prefix) is None
    }


@lru_cache(maxsize=1)
def get_xrefs_prefix_blacklist() -> Set[str]:
    """Get the set of blacklisted xref prefixes."""
    #: Xrefs starting with these prefixes will be ignored
    return set(
        itt.chain.from_iterable(_get_curated_registry()["blacklists"]["resource_prefix"].values())
    ) | set(_get_curated_registry()["blacklists"]["prefix"])


@lru_cache(maxsize=1)
def get_xrefs_suffix_blacklist() -> Set[str]:
    """Get the set of blacklisted xref suffixes."""
    #: Xrefs ending with these suffixes will be ignored
    return set(_get_curated_registry()["blacklists"]["suffix"])


@lru_cache(maxsize=1)
def get_xrefs_blacklist() -> Set[str]:
    """Get the set of blacklisted xrefs."""
    rv = set()
    for x in _get_curated_registry()["blacklists"]["full"]:
        if isinstance(x, str):
            rv.add(x)
        elif isinstance(x, dict):
            if x.get("type") == "group":
                rv.update(x["text"])
            elif "text" in x:
                rv.add(x["text"])
            else:
                raise ValueError("invalid schema")
        else:
            raise TypeError
    return rv


@lru_cache(maxsize=1)
def get_remappings_full() -> Mapping[str, str]:
    """Get the remappings for xrefs based on the entire xref database."""
    return _get_curated_registry()["remappings"]["full"]


def remap_full(x: str) -> str:
    """Remap the string if possible otherwise return it."""
    return get_remappings_full().get(x, x)


@lru_cache(maxsize=1)
def get_remappings_prefix() -> Mapping[str, str]:
    """Get the remappings for xrefs based on the prefix.

    .. note:: Doesn't take into account the semicolon `:`
    """
    return _get_curated_registry()["remappings"]["prefix"]


def iter_cached_obo() -> List[Tuple[str, str]]:
    """Iterate over cached OBO paths."""
    for prefix in os.listdir(RAW_DIRECTORY):
        if prefix in GLOBAL_SKIP or has_no_download(prefix) or bioregistry.is_deprecated(prefix):
            continue
        d = os.path.join(RAW_DIRECTORY, prefix)
        if not os.path.isdir(d):
            continue
        for x in os.listdir(d):
            if x.endswith(".obo"):
                p = os.path.join(d, x)
                yield prefix, p
