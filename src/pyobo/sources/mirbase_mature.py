# -*- coding: utf-8 -*-

"""Converter for miRBase Mature."""

from typing import Iterable

from tqdm import tqdm

from .mirbase_constants import get_mature_df
from ..struct import Obo, Reference, Synonym, Term

__all__ = [
    "MiRBaseMatureGetter",
]

PREFIX = "mirbase.mature"


class MiRBaseMatureGetter(Obo):
    ontology = PREFIX
    bioversions_key = "mirbase"

    def iter_terms(self, force: bool = False) -> Iterable[Term]:
        return iter_terms(version=self.data_version, force=force)


def get_obo(force: bool = False) -> Obo:
    """Get miRBase mature as OBO."""
    return MiRBaseMatureGetter(force=force)


def iter_terms(version: str, force: bool = False) -> Iterable[Term]:
    """Get miRBase mature terms."""
    df = get_mature_df(version, force=force)
    for name, previous_name, mirbase_mature_id in tqdm(df.values, total=len(df.index)):
        yield Term(
            reference=Reference(prefix=PREFIX, identifier=mirbase_mature_id, name=name),
            synonyms=[
                Synonym(name=previous_name),
            ],
        )


if __name__ == "__main__":
    get_obo().write_default(use_tqdm=True)
