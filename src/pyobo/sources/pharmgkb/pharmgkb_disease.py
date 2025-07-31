"""An ontology representation of PharmGKB phenotypes."""

from collections.abc import Iterable
from typing import cast

import pandas as pd

from pyobo import Obo, Reference, Term
from pyobo.sources.pharmgkb.utils import download_pharmgkb_tsv, parse_xrefs, split

__all__ = [
    "PharmGKBDiseaseGetter",
]

PREFIX = "pharmgkb.disease"
URL = "https://api.pharmgkb.org/v1/download/file/data/phenotypes.zip"


class PharmGKBDiseaseGetter(Obo):
    """An ontology representation of PharmGKB phenotypes."""

    ontology = bioversions_key = PREFIX
    dynamic_version = True

    def iter_terms(self, force: bool = False) -> Iterable[Term]:
        """Iterate over terms in the ontology."""
        return iter_terms(force=force)


def iter_terms(force: bool = False) -> Iterable[Term]:
    """Iterate over terms.

    :param force: Should the data be re-downloaded

    :yields: Terms

    1. PharmGKB Accession Id = Identifier assigned to this phenotype by PharmGKB
    2. Name = Name PharmGKB uses for this phenotype
    3. Alternate Names = Other known names for this phenotype, comma-separated
    4. Cross-references = References to other resources in the form "resource:id",
       comma-separated
    5. External Vocabulary = Term for this phenotype in another vocabulary in the form
       "vocabulary:id", comma-separated
    """
    df = download_pharmgkb_tsv(PREFIX, url=URL, inner="phenotypes.tsv", force=force)
    for _, row in df.iterrows():
        identifier = row["PharmGKB Accession Id"]
        if pd.isna(identifier):
            continue
        name = row["Name"]
        term = Term.from_triple(PREFIX, identifier=str(identifier), name=name)

        synonyms = set()
        for synonym in split(row, "Alternate Names"):
            synonym = synonym.strip()
            if synonym.casefold() == name.casefold():
                continue
            synonyms.add(synonym.strip('"'))
        for synonym in sorted(synonyms):
            term.append_synonym(synonym)
        for xref in parse_xrefs(term, row):
            term.append_xref(xref)

        for xref_line in split(row, "External Vocabulary"):
            xref_curie, _, _ = xref_line.strip('"').partition("(")
            try:
                xref = cast(Reference, Reference.from_curie(xref_curie))
            except Exception:  # noqa:S110
                pass  # this happens when there's a comma in the name, but not a problem
            else:
                term.append_xref(xref)

        yield term


if __name__ == "__main__":
    PharmGKBDiseaseGetter.cli()
