# -*- coding: utf-8 -*-

"""Selventa diseases.

.. seealso:: https://github.com/pyobo/pyobo/issues/26
"""

from typing import Iterable, Optional

import pandas as pd

from pyobo import Obo, Term
from pyobo.utils.path import ensure_df

PREFIX = "sdis"
URL = "https://raw.githubusercontent.com/OpenBEL/resource-generator/master/datasets/selventa-legacy-diseases.txt"


def get_obo(*, force: bool = False) -> Obo:
    """Get Selventa Diseases as OBO."""
    return Obo(
        ontology=PREFIX,
        name="Selventa Diseases",
        iter_terms=iter_terms,
        iter_terms_kwargs=dict(force=force),
        data_version="1.0.0",
        auto_generated_by=f"bio2obo:{PREFIX}",
    )


def iter_terms(force: Optional[bool] = False) -> Iterable[Term]:
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
    get_obo().write_default(write_obo=True, force=True)
