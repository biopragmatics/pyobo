"""Converter for CPT."""

from collections.abc import Iterable

import pandas as pd

from pyobo import Obo, Reference, Term

__all__ = [
    "CPTGetter",
]

cpt_url = "https://www2a.cdc.gov/vaccines/iis/iisstandards/downloads/cpt.txt"
PREFIX = "cpt"


class CPTGetter(Obo):
    """An ontology representation of CPT."""

    ontology = PREFIX
    dynamic_version = True

    def iter_terms(self, force: bool = False) -> Iterable[Term]:
        """Iterate over terms in the ontology."""
        return iter_terms()


def iter_terms() -> Iterable[Term]:
    """Iterate over CPT terms."""
    df = pd.read_csv(
        cpt_url,
        sep="|",
        names=[
            "cpt",
            "description",
            "...",
            "vaccine_name",
            "cvx",
            "comments",
            "updated",
            "internal_id",
        ],
        dtype=str,
    )
    del df["..."]
    for col in df.columns:
        df[col] = df[col].map(lambda s: s.strip() if pd.notna(s) else s)
    for cpt_id, description, name, cvx, comments, _updated, _internal_id in df.values:
        term = Term(
            reference=Reference(prefix=PREFIX, identifier=cpt_id, name=name),
            definition=description,
        )
        if pd.notna(cvx):
            term.append_xref(Reference(prefix="cvx", identifier=cvx))
        if pd.notna(comments):
            term.append_comment(comments)
        yield term


if __name__ == "__main__":
    CPTGetter.cli()
