"""Selventa diseases.

.. seealso::

    https://github.com/pyobo/pyobo/issues/26
"""

from collections.abc import Iterable

import pandas as pd

from pyobo import Obo, Term
from pyobo.utils.path import ensure_df

__all__ = [
    "SDISGetter",
]

PREFIX = "sdis"
URL = "https://raw.githubusercontent.com/OpenBEL/resource-generator/master/datasets/selventa-legacy-diseases.txt"


class SDISGetter(Obo):
    """An ontology representation of the Selventa disease nomenclature."""

    ontology = PREFIX
    static_version = "1.0.0"

    def iter_terms(self, force: bool = False) -> Iterable[Term]:
        """Iterate over terms in the ontology."""
        return iter_terms(force=force)


def iter_terms(force: bool = False) -> Iterable[Term]:
    """Iterate over selventa disease terms."""
    df = ensure_df(PREFIX, url=URL, skiprows=9, force=force)

    for identifier, label, synonyms, xrefs in df[["ID", "LABEL", "SYNONYMS", "XREF"]].values:
        term = Term.from_triple(PREFIX, identifier, label)
        for synonym in synonyms.split("|") if pd.notna(synonyms) else []:
            term.append_synonym(synonym)
        for xref in xrefs.split("|") if pd.notna(xrefs) else []:
            term.append_xref(xref)
        yield term


if __name__ == "__main__":
    SDISGetter.cli()
