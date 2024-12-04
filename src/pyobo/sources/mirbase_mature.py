"""Converter for miRBase Mature."""

from collections.abc import Iterable

import pandas as pd
from tqdm.auto import tqdm

from pyobo.sources.mirbase_constants import get_mature_df
from pyobo.struct import Obo, Reference, Synonym, Term

__all__ = [
    "MiRBaseMatureGetter",
]

PREFIX = "mirbase.mature"


class MiRBaseMatureGetter(Obo):
    """An ontology representation of miRBase's mature miRNA nomenclature."""

    ontology = PREFIX
    bioversions_key = "mirbase"

    def iter_terms(self, force: bool = False) -> Iterable[Term]:
        """Iterate over terms in the ontology."""
        return iter_terms(version=self._version_or_raise, force=force)


def get_obo(force: bool = False) -> Obo:
    """Get miRBase mature as OBO."""
    return MiRBaseMatureGetter(force=force)


def iter_terms(version: str, force: bool = False) -> Iterable[Term]:
    """Get miRBase mature terms."""
    df = get_mature_df(version, force=force)
    for _, name, previous_name, mirbase_mature_id in tqdm(
        df.values, total=len(df.index), unit_scale=True
    ):
        synonyms = []
        if pd.notna(previous_name):
            synonyms.append(Synonym(name=previous_name))
        yield Term(
            reference=Reference(
                prefix=PREFIX, identifier=mirbase_mature_id, name=name if pd.notna(name) else None
            ),
            synonyms=synonyms,
        )


if __name__ == "__main__":
    get_obo().write_default(write_obo=True, write_obograph=True, use_tqdm=True)
