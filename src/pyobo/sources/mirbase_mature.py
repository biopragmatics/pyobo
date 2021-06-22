# -*- coding: utf-8 -*-

"""Converter for miRBase Mature."""

from typing import Iterable

import bioversions
from tqdm import tqdm

from .mirbase_constants import get_mature_df
from ..struct import Obo, Reference, Synonym, Term

PREFIX = "mirbase.mature"


def get_obo() -> Obo:
    """Get miRBase mature as OBO."""
    version = bioversions.get_version("mirbase")
    return Obo(
        ontology=PREFIX,
        name="miRBase Mature",
        auto_generated_by=f"bio2obo:{PREFIX}",
        data_version=version,
        iter_terms=iter_terms,
        iter_terms_kwargs=dict(version=version),
    )


def iter_terms(version: str) -> Iterable[Term]:
    """Get miRBase mature terms."""
    df = get_mature_df(version)
    for name, previous_name, mirbase_mature_id in tqdm(df.values, total=len(df.index)):
        yield Term(
            reference=Reference(prefix=PREFIX, identifier=mirbase_mature_id, name=name),
            synonyms=[
                Synonym(name=previous_name),
            ],
        )


if __name__ == "__main__":
    get_obo().write_default(use_tqdm=True)
