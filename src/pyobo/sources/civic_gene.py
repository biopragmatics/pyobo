"""Converter for CiVIC Genes."""

import datetime
from collections.abc import Iterable

import pandas as pd

from pyobo.struct import Obo, Reference, Term, int_identifier_sort_key
from pyobo.utils.path import ensure_df

__all__ = [
    "CIVICGeneGetter",
]

PREFIX = "civic.gid"
URL = "https://civicdb.org/downloads/nightly/nightly-GeneSummaries.tsv"


class CIVICGeneGetter(Obo):
    """An ontology representation of CiVIC's gene nomenclature."""

    bioversions_key = ontology = PREFIX
    term_sort_key = int_identifier_sort_key

    def iter_terms(self, force: bool = False) -> Iterable[Term]:
        """Iterate over gene terms for CiVIC."""
        yield from get_terms(self._version_or_raise, force=force)


def get_terms(version: str, force: bool = False) -> Iterable[Term]:
    """Get CIVIC terms."""
    dt = datetime.datetime.strptime(version, "%Y-%m-%d")
    # version is like 01-Feb-2024
    dt2 = datetime.datetime.strftime(dt, "%d-%b-%Y")
    url = f"https://civicdb.org/downloads/{dt2}/{dt2}-GeneSummaries.tsv"
    df = ensure_df(prefix=PREFIX, url=url, sep="\t", force=force, dtype=str, version=version)
    for identifier, _, name, entrez_id, description, _last_review, _flag in df.values:
        term = Term(
            reference=Reference(prefix=PREFIX, identifier=identifier, name=name),
            definition=description if pd.notna(description) else None,
        )
        term.append_exact_match(Reference(prefix="ncbigene", identifier=entrez_id))
        yield term


if __name__ == "__main__":
    CIVICGeneGetter.cli()
