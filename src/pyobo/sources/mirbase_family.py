# -*- coding: utf-8 -*-

"""Converter for miRBase Families."""

from typing import Iterable

import bioversions
import pandas as pd
from tqdm import tqdm


from .mirbase_constants import (
    get_premature_df,
    get_premature_family_df,
    get_premature_to_prefamily_df,
)
from ..struct import Obo, Reference, Term, has_member

PREFIX = "mirbase.family"


def get_obo() -> Obo:
    """Get miRBase family as OBO."""
    version = bioversions.get_version("mirbase")
    return Obo(
        ontology=PREFIX,
        name="miRBase Families",
        auto_generated_by=f"bio2obo:{PREFIX}",
        data_version=version,
        iter_terms=iter_terms,
        iter_terms_kwargs=dict(version=version),
    )


def iter_terms(version: str) -> Iterable[Term]:
    """Get miRBase family terms."""
    df = get_df(version)
    for family_id, name, mirna_id, mirna_name in tqdm(df.values, total=len(df.index)):
        term = Term(
            reference=Reference(prefix=PREFIX, identifier=family_id, name=name),
        )
        term.append_relationship(
            has_member, Reference(prefix="mirna", identifier=mirna_id, name=mirna_name)
        )
        yield term


def get_df(version: str) -> pd.DataFrame:
    """Get the miRBase family dataframe."""
    mirna_prefamily_df = get_premature_to_prefamily_df(version)
    prefamily_df = get_premature_family_df(version)
    premature_df = get_premature_df(version)
    rv = mirna_prefamily_df.join(prefamily_df, on="prefamily_key").join(
        premature_df, on="premature_key"
    )
    del rv["premature_key"]
    del rv["prefamily_key"]
    return rv


if __name__ == "__main__":
    get_obo().write_default(use_tqdm=True)
