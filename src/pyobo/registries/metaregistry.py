"""Load the manually curated metaregistry."""

import itertools as itt
import json
import os
from collections.abc import Iterable, Mapping
from functools import lru_cache
from pathlib import Path

import bioregistry

from ..constants import GLOBAL_SKIP, RAW_DIRECTORY

HERE = Path(__file__).parent.resolve()
CURATED_REGISTRY_PATH = HERE.joinpath("metaregistry.json")
CURATED_REGISTRY = json.loads(CURATED_REGISTRY_PATH.read_text())


def has_no_download(prefix: str) -> bool:
    """Return if the prefix is not available."""
    prefix_norm = bioregistry.normalize_prefix(prefix)
    return prefix_norm is not None and prefix_norm in _no_download()


@lru_cache(maxsize=1)
def _no_download() -> set[str]:
    """Get the list of prefixes not available as OBO."""
    return {
        prefix
        for prefix in bioregistry.read_registry()
        if bioregistry.get_obo_download(prefix) is None
        and bioregistry.get_owl_download(prefix) is None
    }


def curie_has_blacklisted_prefix(curie: str) -> bool:
    """Check if the CURIE string has a blacklisted prefix."""
    return any(curie.startswith(x) for x in get_xrefs_prefix_blacklist())


@lru_cache(maxsize=1)
def get_xrefs_prefix_blacklist() -> set[str]:
    """Get the set of blacklisted xref prefixes."""
    #: Xrefs starting with these prefixes will be ignored
    prefixes = set(
        itt.chain.from_iterable(CURATED_REGISTRY["blacklists"]["resource_prefix"].values())
    ) | set(CURATED_REGISTRY["blacklists"]["prefix"])
    nonsense = {
        prefix
        for prefix in prefixes
        if bioregistry.normalize_prefix(prefix.rstrip(":")) is not None
    }
    if nonsense:
        raise ValueError(
            f"The following prefixes were blacklisted but are in the bioregistry: {nonsense}"
        )
    return prefixes


def curie_has_blacklisted_suffix(curie: str) -> bool:
    """Check if the CURIE string has a blacklisted suffix."""
    return any(curie.endswith(suffix) for suffix in get_xrefs_suffix_blacklist())


@lru_cache(maxsize=1)
def get_xrefs_suffix_blacklist() -> set[str]:
    """Get the set of blacklisted xref suffixes."""
    #: Xrefs ending with these suffixes will be ignored
    return set(CURATED_REGISTRY["blacklists"]["suffix"])


def curie_is_blacklisted(curie: str) -> bool:
    """Check if the full CURIE string is blacklisted."""
    return curie in get_xrefs_blacklist()


@lru_cache(maxsize=1)
def get_xrefs_blacklist() -> set[str]:
    """Get the set of blacklisted xrefs."""
    rv = set()
    for x in CURATED_REGISTRY["blacklists"]["full"]:
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
    return CURATED_REGISTRY["remappings"]["full"]


def remap_full(x: str) -> str:
    """Remap the string if possible otherwise return it."""
    return get_remappings_full().get(x, x)


@lru_cache(maxsize=1)
def get_remappings_prefix() -> Mapping[str, str]:
    """Get the remappings for xrefs based on the prefix.

    .. note:: Doesn't take into account the semicolon `:`
    """
    return CURATED_REGISTRY["remappings"]["prefix"]


def remap_prefix(curie: str) -> str:
    """Remap a prefix."""
    for old_prefix, new_prefix in get_remappings_prefix().items():
        if curie.startswith(old_prefix):
            return new_prefix + curie[len(old_prefix) :]
    return curie


def iter_cached_obo() -> Iterable[tuple[str, str]]:
    """Iterate over cached OBO paths."""
    for prefix in os.listdir(RAW_DIRECTORY):
        if prefix in GLOBAL_SKIP or has_no_download(prefix) or bioregistry.is_deprecated(prefix):
            continue
        d = RAW_DIRECTORY.joinpath(prefix)
        if not os.path.isdir(d):
            continue
        for x in os.listdir(d):
            if x.endswith(".obo"):
                p = os.path.join(d, x)
                yield prefix, p
