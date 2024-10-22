"""Converter for CiVIC Genes."""

from collections.abc import Iterable
from typing import Optional

import pandas as pd

from pyobo.struct import Obo, Reference, Term
from pyobo.utils.path import ensure_df

__all__ = [
    "CIVICGeneGetter",
]

PREFIX = "civic.gid"
URL = "https://civicdb.org/downloads/nightly/nightly-GeneSummaries.tsv"


def _sort(_o, t):
    return int(t.identifier)


class CIVICGeneGetter(Obo):
    """An ontology representation of CiVIC's gene nomenclature."""

    bioversions_key = ontology = PREFIX
    term_sort_key = _sort

    def iter_terms(self, force: bool = False) -> Iterable[Term]:
        """Iterate over gene terms for CiVIC."""
        yield from get_terms(self.data_version, force=force)


def get_terms(version: Optional[str] = None, force: bool = False) -> Iterable[Term]:
    """Get CIVIC terms."""
    # if version is not None:
    #     version_dt: datetime.date = dateutil.parser.parse(version)
    # else:
    #     version_dt: datetime.date = datetime.today()
    # version = version_dt.strftime("01-%b-%Y")
    # version is like 01-Feb-2024
    url = f"https://civicdb.org/downloads/{version}/{version}-GeneSummaries.tsv"
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
