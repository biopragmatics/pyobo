"""Selventa families."""

from collections.abc import Iterable

import pandas as pd

from pyobo import Obo, Term
from pyobo.utils.path import ensure_df

__all__ = [
    "SFAMGetter",
]

URL = "https://raw.githubusercontent.com/OpenBEL/resource-generator/master/datasets/selventa-protein-families.txt"
PREFIX = "sfam"


class SFAMGetter(Obo):
    """An ontology representation of the Selventa protein family nomenclature."""

    ontology = PREFIX
    static_version = "1.0.0"

    def iter_terms(self, force: bool = False) -> Iterable[Term]:
        """Iterate over terms in the ontology."""
        return iter_terms(force=force)


def iter_terms(force: bool = False) -> Iterable[Term]:
    """Iterate over selventa family terms."""
    df = ensure_df(PREFIX, url=URL, skiprows=9, force=force)

    terms = {}
    for identifier, label, synonyms in df[["ID", "LABEL", "SYNONYMS"]].values:
        term = Term.from_triple(PREFIX, identifier, label)
        for synonym in synonyms.split("|") if pd.notna(synonyms) else []:
            term.append_synonym(synonym)
        terms[identifier] = term

    df.PARENTS = df.PARENTS.map(lambda x: x[len("SFAM:") :], na_action="ignore")
    for child, parent in df.loc[df.PARENTS.notna(), ["ID", "PARENTS"]].values:
        if child == parent:
            continue  # wow...
        terms[child].append_parent(terms[parent])

    yield from terms.values()


if __name__ == "__main__":
    SFAMGetter.cli()
