# -*- coding: utf-8 -*-

"""Selventa chemicals.

.. seealso:: https://github.com/pyobo/pyobo/issues/27
"""

from typing import Iterable, Optional

import pandas as pd

from pyobo import Obo, Term
from pyobo.utils.path import ensure_df

PREFIX = "schem"
URL = "https://raw.githubusercontent.com/OpenBEL/resource-generator/master/datasets/selventa-legacy-chemical-names.txt"


def get_obo(*, force: bool = False) -> Obo:
    """Get Selventa chemical as OBO."""
    return Obo(
        ontology=PREFIX,
        name="Selventa Chemicals",
        iter_terms=iter_terms,
        iter_terms_kwargs=dict(force=force),
        data_version="1.0.0",
        auto_generated_by=f"bio2obo:{PREFIX}",
    )


def iter_terms(force: Optional[bool] = False) -> Iterable[Term]:
    """Iterate over selventa chemical terms."""
    df = ensure_df(PREFIX, url=URL, skiprows=8, force=force)
    for identifier, label, xrefs in df[["ID", "LABEL", "XREF"]].values:
        term = Term.from_triple(PREFIX, identifier, label)
        for xref in xrefs.split("|") if pd.notna(xrefs) else []:
            term.append_xref(xref)
        yield term


if __name__ == "__main__":
    get_obo().write_default(write_obo=True, force=True)
