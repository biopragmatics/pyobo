"""Shared code for geonames sources."""

from __future__ import annotations

from collections.abc import Iterable

import pandas as pd
from tqdm import tqdm

from pyobo import Reference, Term, TypeDef, default_reference
from pyobo.struct.struct import CHARLIE_TERM, HUMAN_TERM, PYOBO_INJECTED
from pyobo.utils.path import ensure_df

PREFIX = "geonames"
PREFIX_FEATURE = "geonames.feature"

FEATURES_URL = "https://download.geonames.org/export/dump/featureCodes_en.txt"
COUNTRIES_URL = "https://download.geonames.org/export/dump/countryInfo.txt"
ADMIN1_URL = "https://download.geonames.org/export/dump/admin1CodesASCII.txt"
ADMIN2_URL = "https://download.geonames.org/export/dump/admin2Codes.txt"
CITIES_URL = "https://download.geonames.org/export/dump/cities15000.zip"
SYNONYMS_URL = "https://download.geonames.org/export/dump/alternateNamesV2.zip"

# External parent classes
CITY = Reference(prefix="ENVO", identifier="00000856", name="city")
NATION = Reference(prefix="ENVO", identifier="00000009", name="national geopolitical entity")
ADMIN_1 = Reference(prefix="ENVO", identifier="00000005", name="first-order administrative region")
ADMIN_2 = Reference(prefix="ENVO", identifier="00000006", name="second-order administrative region")

# Builtin classes
FEATURE = default_reference(PREFIX_FEATURE, "feature", "GeoNames feature")
FEATURE_TERM = Term(reference=FEATURE)

# Type definitions
CODE_TYPEDEF = TypeDef(
    reference=default_reference(PREFIX, "code", name="GeoNames code"), is_metadata_tag=True
)

SYNONYMS_DF_COLUMNS = [
    "id",
    "geonames_id",
    "iso_lang",
    "synonym",
    "is_preferred",
    "is_short",
    "is_colloquial",
    "is_historic",
    "start_time",
    "end_time",
]

P_CATEGORY = default_reference(PREFIX_FEATURE, "P", "city feature")

FEATURE_CATEGORIES = {
    "A": default_reference(PREFIX_FEATURE, "A", "geopolitical feature"),
    "H": default_reference(PREFIX_FEATURE, "H", "aquatic feature"),
    "V": default_reference(PREFIX_FEATURE, "V", "floral feature feature"),
    "S": default_reference(PREFIX_FEATURE, "S", "building feature"),
    "U": default_reference(PREFIX_FEATURE, "U", "undersea feature"),
    "T": default_reference(PREFIX_FEATURE, "T", "geographic feature"),
    "L": default_reference(PREFIX_FEATURE, "L", "parks feature"),
    "P": P_CATEGORY,
    "R": default_reference(PREFIX_FEATURE, "R", "road or rail feature"),
}


def get_features(*, force: bool = False) -> dict[str, Term]:
    """Get all features."""
    df = ensure_df(
        PREFIX,
        url=FEATURES_URL,
        force=force,
        keep_default_na=False,  # NA is a country code
        dtype=str,
    )
    rv = {}
    for identifier, name, description in df.values:
        if pd.isna(identifier) or identifier == "null":
            continue

        term = Term(
            reference=Reference(
                prefix=PREFIX_FEATURE, identifier=identifier, name=name if pd.notna(name) else None
            ),
            definition=description if pd.notna(description) else None,
        )
        parent_letter, _, rest = identifier.partition(".")
        if not rest:
            tqdm.write(f"[{PREFIX_FEATURE}] unhandled identifier: {identifier}")
        elif parent_letter not in FEATURE_CATEGORIES:
            tqdm.write(f"[{PREFIX_FEATURE}] unhandled category: {parent_letter}")
        else:
            term.append_parent(FEATURE_CATEGORIES[parent_letter])

        rv[identifier] = term
    return rv


def get_feature_terms(
    force: bool = False, features: dict[str, Term] | None = None
) -> Iterable[Term]:
    """Get terms for GeoNames features."""
    yield FEATURE_TERM
    yield HUMAN_TERM
    yield CHARLIE_TERM
    for cat in FEATURE_CATEGORIES.values():
        yield (
            Term(reference=cat)
            .append_parent(FEATURE_TERM)
            .append_contributor(CHARLIE_TERM)
            .append_comment(PYOBO_INJECTED)
        )
    if features is None:
        features = get_features(force=force)
    yield from features.values()
