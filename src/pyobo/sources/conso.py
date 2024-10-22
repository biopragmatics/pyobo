"""Converter for CONSO."""

from collections.abc import Iterable

import pandas as pd

from ..struct import Obo, Reference, Synonym, Term
from ..utils.io import multidict
from ..utils.path import ensure_df

__all__ = [
    "CONSOGetter",
]

PREFIX = "conso"
BASE_URL = "https://raw.githubusercontent.com/pharmacome/conso/master/src/conso/resources"
TERMS_URL = f"{BASE_URL}/terms.tsv"
RELATIONS_URL = f"{BASE_URL}/relations.tsv"
TYPEDEFS_URL = f"{BASE_URL}/typedefs.tsv"
SYNONYMS_URL = f"{BASE_URL}/synonyms.tsv"


class CONSOGetter(Obo):
    """An ontology representation of CONSO vocabulary."""

    ontology = PREFIX
    dynamic_version = True

    def iter_terms(self, force: bool = False) -> Iterable[Term]:
        """Iterate over terms in the ontology."""
        return iter_terms()


def get_obo() -> Obo:
    """Get CONSO as OBO."""
    return CONSOGetter()


def iter_terms() -> Iterable[Term]:
    """Get CONSO terms."""
    terms_df = ensure_df(PREFIX, url=TERMS_URL)

    synonyms_df = ensure_df(PREFIX, url=SYNONYMS_URL)
    synonyms_df["reference"] = synonyms_df["reference"].map(
        lambda s: [Reference.from_curie(s)] if pd.notna(s) and s != "?" else [],
    )
    synonyms_df["specificity"] = synonyms_df["specificity"].map(
        lambda s: "EXACT" if pd.isna(s) or s == "?" else s
    )

    synonyms = multidict(
        (
            identifier,
            Synonym(
                name=synonym,
                provenance=provenance,
                specificity=specificity,
            ),
        )
        for identifier, synonym, provenance, specificity in synonyms_df.values
    )

    # TODO later
    # relations_df = ensure_df(PREFIX, RELATIONS_URL)

    for _, row in terms_df.iterrows():
        if row["Name"] == "WITHDRAWN":
            continue
        provenance: list[Reference] = []
        for curie in row["References"].split(","):
            curie = curie.strip()
            if not curie:
                continue
            reference = Reference.from_curie(curie)
            if reference is not None:
                provenance.append(reference)
        identifier = row["Identifier"]
        yield Term(
            reference=Reference(prefix=PREFIX, identifier=identifier, name=row["Name"]),
            definition=row["Description"],
            provenance=provenance,
            synonyms=synonyms.get(identifier, []),
        )


if __name__ == "__main__":
    CONSOGetter.cli()
