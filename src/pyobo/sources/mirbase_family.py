"""Converter for miRBase Families."""

from collections.abc import Iterable

import pandas as pd
from tqdm.auto import tqdm

from pyobo.sources.mirbase_constants import (
    get_premature_df,
    get_premature_family_df,
    get_premature_to_prefamily_df,
)
from pyobo.struct import Obo, Reference, Term, has_member

__all__ = [
    "MiRBaseFamilyGetter",
]

PREFIX = "mirbase.family"


class MiRBaseFamilyGetter(Obo):
    """An ontology representation of miRBase's miRNA family nomenclature."""

    ontology = PREFIX
    bioversions_key = "mirbase"
    typedefs = [has_member]

    def iter_terms(self, force: bool = False) -> Iterable[Term]:
        """Iterate over terms in the ontology."""
        return iter_terms(version=self._version_or_raise, force=force)


def get_obo(force: bool = False) -> Obo:
    """Get miRBase family as OBO."""
    return MiRBaseFamilyGetter(force=force)


def iter_terms(version: str, force: bool = False) -> Iterable[Term]:
    """Get miRBase family terms."""
    df = get_df(version, force=force)
    for family_id, name, mirna_id, mirna_name in tqdm(
        df.values, total=len(df.index), unit_scale=True, desc="miRBase Family"
    ):
        term = Term(
            reference=Reference(prefix=PREFIX, identifier=family_id, name=name),
        )
        term.append_relationship(
            has_member, Reference(prefix="mirbase", identifier=mirna_id, name=mirna_name)
        )
        yield term


def get_df(version: str, force: bool = False) -> pd.DataFrame:
    """Get the miRBase family dataframe."""
    mirna_prefamily_df = get_premature_to_prefamily_df(version, force=force)
    prefamily_df = get_premature_family_df(version, force=force)
    premature_df = get_premature_df(version, force=force)
    intermediate_df = pd.merge(
        mirna_prefamily_df, prefamily_df, left_on="prefamily_key", right_on="prefamily_key"
    )
    rv = pd.merge(intermediate_df, premature_df, left_on="premature_key", right_on="premature_key")
    del rv["premature_key"]
    del rv["prefamily_key"]
    return rv


if __name__ == "__main__":
    get_obo().write_default(use_tqdm=True, write_obo=True, force=True)
