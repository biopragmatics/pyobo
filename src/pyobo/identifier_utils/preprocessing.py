"""Load the manually curated metaregistry."""

from functools import lru_cache
from pathlib import Path

from curies.preprocessing import PreprocessingRules, _load_rules

from ..resources.goc import load_goc_map

__all__ = [
    "get_rules",
]

HERE = Path(__file__).parent.resolve()
RULES_PATH = HERE.joinpath("preprocessing.json")


@lru_cache(1)
def get_rules() -> PreprocessingRules:
    """Get the CURIE/URI string preprocessing rules."""
    rules = _load_rules(RULES_PATH.read_text())
    rules.rewrites.full.update(load_goc_map())
    return rules


if __name__ == "__main__":
    PreprocessingRules.lint_file(RULES_PATH)
