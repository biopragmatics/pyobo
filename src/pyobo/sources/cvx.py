# -*- coding: utf-8 -*-

"""Converter for CVX."""

from collections import defaultdict
from typing import Iterable

import pandas as pd

from pyobo import Obo, Term

__all__ = [
    "CVXGetter",
]

cvx_url = "https://www2a.cdc.gov/vaccines/iis/iisstandards/downloads/cvx.txt"
PREFIX = "cvx"


class CVXGetter(Obo):
    """An ontology representation of CVX."""

    ontology = PREFIX
    dynamic_version = True

    def iter_terms(self, force: bool = False) -> Iterable[Term]:
        """Iterate over terms in the ontology."""
        return iter_terms()


def iter_terms() -> Iterable[Term]:
    """Iterate over terms in CVX."""
    dd = defaultdict(set)
    hierarchy_df = pd.read_csv(
        "https://www2a.cdc.gov/vaccines/iis/iisstandards/downloads/VG.txt",
        sep="|",
        usecols=[1, 4],
        dtype=str,
    )
    for col in hierarchy_df.columns:
        hierarchy_df[col] = hierarchy_df[col].map(str.strip)
    for child, parent in hierarchy_df.values:
        dd[child].add(parent)

    cvx_df = pd.read_csv(
        cvx_url,
        sep="|",
        names=[
            "cvx",
            "short_name",
            "full_name",
            "notes",
            "status",
            "nonvaccine",
            "updated",
        ],
        dtype=str,
    )
    for col in cvx_df.columns:
        cvx_df[col] = cvx_df[col].map(lambda s: s.strip() if pd.notna(s) else s)
    terms = {}
    for cvx, short_name, full_name, notes, status, nonvaccine, _updated in cvx_df.values:
        term = Term.from_triple(PREFIX, cvx, full_name)
        if short_name != full_name:
            term.append_synonym(short_name)
        if pd.notna(notes):
            term.append_comment(notes)
        if pd.notna(status):
            term.append_property("status", status)
        if pd.notna(nonvaccine):
            term.append_property("nonvaccine", nonvaccine)
        terms[cvx] = term

    for child, parents in dd.items():
        for parent in sorted(parents):
            parent_term = terms[parent]
            terms[child].append_parent(parent_term)

    return iter(sorted(terms.values(), key=lambda term: int(term.identifier)))


if __name__ == "__main__":
    CVXGetter.cli()
