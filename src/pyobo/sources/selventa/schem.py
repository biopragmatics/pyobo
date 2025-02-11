"""Selventa chemicals.

.. seealso::

    https://github.com/pyobo/pyobo/issues/27
"""

from collections.abc import Iterable

import pandas as pd

from pyobo import Obo, Term
from pyobo.utils.path import ensure_df

__all__ = [
    "SCHEMGetter",
]

PREFIX = "schem"
URL = "https://raw.githubusercontent.com/OpenBEL/resource-generator/master/datasets/selventa-legacy-chemical-names.txt"


class SCHEMGetter(Obo):
    """An ontology representation of the Selventa chemical nomenclature."""

    ontology = PREFIX
    static_version = "1.0.0"

    def iter_terms(self, force: bool = False) -> Iterable[Term]:
        """Iterate over terms in the ontology."""
        return iter_terms(force=force)


def iter_terms(force: bool = False) -> Iterable[Term]:
    """Iterate over selventa chemical terms."""
    df = ensure_df(PREFIX, url=URL, skiprows=8, force=force)
    for identifier, label, xrefs in df[["ID", "LABEL", "XREF"]].values:
        term = Term.from_triple(PREFIX, identifier, label)
        for xref in xrefs.split("|") if pd.notna(xrefs) else []:
            term.append_xref(xref)
        yield term


if __name__ == "__main__":
    SCHEMGetter.cli()
