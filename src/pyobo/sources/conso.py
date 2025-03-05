"""Converter for CONSO."""

from collections.abc import Iterable

import pandas as pd

from ..struct import Obo, Reference, Synonym, Term, _parse_str_or_curie_or_uri, has_citation
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
    typedefs = [has_citation]

    def iter_terms(self, force: bool = False) -> Iterable[Term]:
        """Iterate over terms in the ontology."""
        return iter_terms()


def iter_terms() -> Iterable[Term]:
    """Get CONSO terms."""
    terms_df = ensure_df(PREFIX, url=TERMS_URL)

    synonyms_df = ensure_df(PREFIX, url=SYNONYMS_URL)
    synonyms_df["reference"] = synonyms_df["reference"].map(
        lambda s: [_parse_str_or_curie_or_uri(s)] if pd.notna(s) and s != "?" else [],
    )
    synonyms = multidict(
        (
            identifier,
            Synonym(
                name=synonym,
                provenance=provenance,
                specificity=None if pd.isna(specificity) or specificity == "?" else specificity,
            ),
        )
        for identifier, synonym, provenance, specificity in synonyms_df.values
    )

    # TODO later
    # relations_df = ensure_df(PREFIX, RELATIONS_URL)

    for _, row in terms_df.iterrows():
        if row["Name"] == "WITHDRAWN":
            continue

        identifier = row["Identifier"]
        term = Term(
            reference=Reference(prefix=PREFIX, identifier=identifier, name=row["Name"]),
            definition=row["Description"],
            synonyms=synonyms.get(identifier, []),
        )
        for curie in row["References"].split(","):
            curie = curie.strip()
            if not curie:
                continue
            reference = _parse_str_or_curie_or_uri(curie)
            if reference is not None:
                term.append_provenance(reference)
        yield term


if __name__ == "__main__":
    CONSOGetter.cli()
