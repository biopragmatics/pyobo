"""Load the manually curated metaregistry."""

import itertools as itt
import json
from collections.abc import Mapping
from functools import lru_cache
from pathlib import Path

import bioregistry

from ..resources.goc import load_goc_map

HERE = Path(__file__).parent.resolve()
CURATED_REGISTRY_PATH = HERE.joinpath("metaregistry.json")
CURATED_REGISTRY = json.loads(CURATED_REGISTRY_PATH.read_text())


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
    rv = CURATED_REGISTRY["remappings"]["full"]
    rv.update(load_goc_map())
    return rv


def remap_full(x: str) -> str:
    """Remap the string if possible otherwise return it."""
    return get_remappings_full().get(x, x)


@lru_cache(maxsize=1)
def get_remappings_prefix() -> Mapping[str, str]:
    """Get the remappings for xrefs based on the prefix.

    .. note::

        Doesn't take into account the semicolon `:`
    """
    return CURATED_REGISTRY["remappings"]["prefix"]


@lru_cache
def _get_resource_specific_map(ontology_prefix: str) -> Mapping[str, str]:
    return CURATED_REGISTRY["remappings"]["resource_prefix"].get(ontology_prefix, {})


def remap_prefix(curie: str, ontology_prefix: str | None = None) -> str:
    """Remap a prefix."""
    if ontology_prefix is not None:
        for old_prefix, new_prefix in _get_resource_specific_map(ontology_prefix).items():
            if curie.startswith(old_prefix):
                return new_prefix + curie[len(old_prefix) :]
    for old_prefix, new_prefix in get_remappings_prefix().items():
        if curie.startswith(old_prefix):
            return new_prefix + curie[len(old_prefix) :]
    return curie


def _sort_dict(d):
    if isinstance(d, str):
        return d
    if isinstance(d, list):
        return sorted(d, key=lambda t: (type(t).__name__, t["from"] if isinstance(t, dict) else t))
    if isinstance(d, dict):
        return {k: _sort_dict(v) for k, v in d.items()}
    raise TypeError


def _lint():
    CURATED_REGISTRY_PATH.write_text(
        json.dumps(_sort_dict(CURATED_REGISTRY), sort_keys=True, indent=2)
    )


if __name__ == "__main__":
    _lint()
