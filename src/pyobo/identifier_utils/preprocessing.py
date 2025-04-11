"""Load the manually curated metaregistry."""

import json
from functools import lru_cache
from pathlib import Path

from bioregistry import NormalizedNamableReference

from .model import Rules
from ..resources.goc import load_goc_map

__all__ = [
    "remap_full",
    "remap_prefix",
    "str_is_blacklisted",
]

HERE = Path(__file__).parent.resolve()
RULES_PATH = HERE.joinpath("preprocessing.json")


@lru_cache(1)
def get_rules() -> Rules:
    """Get the CURIE/URI string preprocessing rules."""
    rules = Rules.model_validate_json(RULES_PATH.read_text())
    rules.rewrites.full.update(load_goc_map())
    return rules


def remap_full(
    str_or_curie_or_uri: str, *, ontology_prefix: str | None = None
) -> NormalizedNamableReference | None:
    """Remap the string if possible otherwise return it."""
    return get_rules().remap_full(
        str_or_curie_or_uri, cls=NormalizedNamableReference, ontology_prefix=ontology_prefix
    )


def remap_prefix(str_or_curie_or_uri: str, ontology_prefix: str | None = None) -> str:
    """Remap a prefix."""
    return get_rules().remap_prefix(str_or_curie_or_uri, ontology_prefix=ontology_prefix)


def _lint() -> None:
    rules = Rules.model_validate_json(RULES_PATH.read_text())
    rules.blacklists._sort()
    RULES_PATH.write_text(json.dumps(rules.model_dump(), sort_keys=True, indent=2))


def str_is_blacklisted(str_or_curie_or_uri: str, *, ontology_prefix: str | None = None) -> bool:
    """Check if the full CURIE string is blacklisted."""
    rules = get_rules()
    return (
        rules.str_is_blacklisted_full(str_or_curie_or_uri, ontology_prefix=ontology_prefix)
        or rules.str_has_blacklisted_prefix(str_or_curie_or_uri, ontology_prefix=ontology_prefix)
        or rules.str_has_blacklisted_suffix(str_or_curie_or_uri)
    )


if __name__ == "__main__":
    _lint()
