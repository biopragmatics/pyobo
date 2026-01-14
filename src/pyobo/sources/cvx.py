"""Converter for CVX."""

import re
from collections import defaultdict
from collections.abc import Iterable

import pandas as pd

from pyobo import Obo, Reference, Term, TypeDef, default_reference
from pyobo.struct.struct import acronym

__all__ = [
    "CVXGetter",
]

cvx_url = "https://www2a.cdc.gov/vaccines/iis/iisstandards/downloads/cvx.txt"
PREFIX = "cvx"
STATUS = TypeDef(
    reference=default_reference(PREFIX, "status", name="has status"), is_metadata_tag=True
)
NONVACCINE = TypeDef(reference=default_reference(PREFIX, "nonvaccine"), is_metadata_tag=True)

ACRONYM_RE = re.compile("^[A-Z]+$")


class CVXGetter(Obo):
    """An ontology representation of CVX."""

    ontology = PREFIX
    dynamic_version = True
    synonym_typedefs = [acronym]
    typedefs = [STATUS, NONVACCINE]

    def iter_terms(self, force: bool = False) -> Iterable[Term]:
        """Iterate over terms in the ontology."""
        return iter_terms()


# This got split, which it's not obvious how to deal with this
MANUAL_OBSOLETE = {"15"}
REPLACEMENTS = {"31": "85", "154": "86", "180": "13"}


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
        if cvx == "99":
            continue  # this is a placeholder

        is_obsolete = cvx in MANUAL_OBSOLETE or (pd.notna(notes) and "do not use" in notes.lower())
        term = Term(
            reference=Reference(prefix=PREFIX, identifier=cvx, name=full_name),
            is_obsolete=is_obsolete,
        )
        if (
            short_name.casefold()
            == full_name.casefold()
            .replace("virus vaccine", "")
            .replace("vaccine", "")
            .replace("  ", " ")
            .strip()
        ):
            pass
        elif short_name != full_name:
            if ACRONYM_RE.match(short_name):
                term.append_exact_synonym(short_name, type=acronym.reference)
            else:
                term.append_synonym(short_name)
        if pd.notna(notes):
            term.append_comment(notes)
        if is_obsolete:
            replacement_identifier = REPLACEMENTS.get(cvx)
            if replacement_identifier:
                term.append_replaced_by(Reference(prefix=PREFIX, identifier=replacement_identifier))
        if pd.notna(status):
            term.annotate_string(STATUS, status)
        if pd.notna(nonvaccine):
            term.annotate_boolean(NONVACCINE, nonvaccine)
        terms[cvx] = term

    for child, parents in dd.items():
        for parent in sorted(parents):
            parent_term = terms[parent]
            terms[child].append_parent(parent_term)

    return iter(sorted(terms.values(), key=lambda term: int(term.identifier)))


if __name__ == "__main__":
    CVXGetter.cli()
