"""Converter for GARD."""

from collections.abc import Iterable

import requests

from pyobo.struct import Obo, Term, default_reference

__all__ = [
    "GARDGetter",
]

PREFIX = "gard"
PP = "gard.category"
URL = "https://rarediseases.info.nih.gov/assets/diseases.trimmed.json"


class GARDGetter(Obo):
    """An ontology representation of GARD."""

    bioversions_key = ontology = PREFIX
    dynamic_version = True

    def iter_terms(self, force: bool = False) -> Iterable[Term]:
        """Iterate over gene terms for GARD."""
        yield from get_terms()


def get_terms() -> Iterable[Term]:
    """Get GARD terms."""
    rows = requests.get(URL, timeout=5).json()
    categories = {
        category: default_reference(
            prefix=PREFIX, identifier=category.lower().replace(" ", "_"), name=category
        )
        for row in rows
        for category in row.get("diseaseCategories", [])
    }
    categories["uncategorized"] = default_reference(
        prefix=PREFIX, identifier="uncategorized", name="Uncategorized Disease"
    )
    for category_reference in categories.values():
        yield Term(reference=category_reference)

    for row in rows:
        term = Term.from_triple(PREFIX, identifier=str(row.pop("id")), name=row.pop("name"))
        _name = row.pop("encodedName", None)
        for synonym in row.pop("synonyms", []):
            synonym = synonym.strip()
            if synonym:
                term.append_synonym(synonym)
        for category in row.pop("diseaseCategories", ["uncategorized"]):
            term.append_parent(categories[category])

        _spanish_id = row.pop("spanishId", None)
        _spanish_name = row.pop("spanishName", None)

        yield term


if __name__ == "__main__":
    GARDGetter().cli()
