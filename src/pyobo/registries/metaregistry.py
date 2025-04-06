"""Load the manually curated metaregistry."""

import json
from functools import lru_cache
from pathlib import Path

from bioregistry import NormalizedNamableReference

from pyobo.registries.model import Rules
from pyobo.resources.goc import load_goc_map

__all__ = [
    "remap_full",
    "remap_prefix",
    "str_has_blacklisted_prefix",
    "str_has_blacklisted_suffix",
    "str_is_blacklisted",
]

HERE = Path(__file__).parent.resolve()
CURATED_REGISTRY_PATH = HERE.joinpath("metaregistry.json")


@lru_cache(1)
def get_rules() -> Rules:
    """Get the rulezzzz."""
    rules = Rules.model_validate_json(CURATED_REGISTRY_PATH.read_text())
    rules.rewrites.full.update(load_goc_map())
    return rules


def str_has_blacklisted_prefix(
    str_or_curie_or_uri: str, *, ontology_prefix: str | None = None
) -> bool:
    """Check if the CURIE string has a blacklisted prefix."""
    blacklists = get_rules().blacklists
    if ontology_prefix:
        prefixes: list[str] = blacklists.resource_prefix.get(ontology_prefix, [])
        if prefixes and any(str_or_curie_or_uri.startswith(prefix) for prefix in prefixes):
            return True
    return any(str_or_curie_or_uri.startswith(prefix) for prefix in blacklists.prefix)


def str_has_blacklisted_suffix(str_or_curie_or_uri: str) -> bool:
    """Check if the CURIE string has a blacklisted suffix."""
    return any(str_or_curie_or_uri.endswith(suffix) for suffix in get_rules().blacklists.suffix)


def str_is_blacklisted(str_or_curie_or_uri: str, *, ontology_prefix: str | None = None) -> bool:
    """Check if the full CURIE string is blacklisted."""
    blacklists = get_rules().blacklists
    if ontology_prefix and str_or_curie_or_uri in blacklists.resource_full.get(
        ontology_prefix, set()
    ):
        return True
    return str_or_curie_or_uri in blacklists.full


def remap_full(
    str_or_curie_or_uri: str, *, ontology_prefix: str | None = None
) -> NormalizedNamableReference | None:
    """Remap the string if possible otherwise return it."""
    rewrites = get_rules().rewrites
    if ontology_prefix:
        resource_rewrites: dict[str, str] = rewrites.resource_full.get(ontology_prefix, {})
        if resource_rewrites and str_or_curie_or_uri in resource_rewrites:
            return NormalizedNamableReference.from_curie(resource_rewrites[str_or_curie_or_uri])

    if str_or_curie_or_uri in rewrites.full:
        return NormalizedNamableReference.from_curie(rewrites.full[str_or_curie_or_uri])

    return None


def remap_prefix(str_or_curie_or_uri: str, ontology_prefix: str | None = None) -> str:
    """Remap a prefix."""
    rewrites = get_rules().rewrites
    if ontology_prefix is not None:
        for old_prefix, new_prefix in rewrites.resource_prefix.get(ontology_prefix, {}).items():
            if str_or_curie_or_uri.startswith(old_prefix):
                return new_prefix + str_or_curie_or_uri[len(old_prefix) :]
    for old_prefix, new_prefix in rewrites.prefix.items():
        if str_or_curie_or_uri.startswith(old_prefix):
            return new_prefix + str_or_curie_or_uri[len(old_prefix) :]
    return str_or_curie_or_uri


def _lint() -> None:
    rules = Rules.model_validate_json(CURATED_REGISTRY_PATH.read_text())
    rules.blacklists._sort()
    CURATED_REGISTRY_PATH.write_text(json.dumps(rules.model_dump(), sort_keys=True, indent=2))


if __name__ == "__main__":
    _lint()
