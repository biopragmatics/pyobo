"""Converter for CiVIC Genes."""

import datetime
from collections.abc import Iterable

import pandas as pd

from pyobo import default_reference
from pyobo.struct import Obo, Reference, Term, TypeDef
from pyobo.utils.path import ensure_df

__all__ = [
    "CIVICGeneGetter",
]

PREFIX = "civic.gid"
URL = "https://civicdb.org/downloads/nightly/nightly-GeneSummaries.tsv"

GENE = Term(reference=default_reference(PREFIX, "gene", name="gene"))
FACTOR = Term(reference=default_reference(PREFIX, "factor", name="factor"))
FUSION = Term(reference=default_reference(PREFIX, "fusion", name="fusion"))
HAS_3P = TypeDef.default(PREFIX, "has3p", name="has 3' gene", is_metadata_tag=False)
HAS_5P = TypeDef.default(PREFIX, "has5p", name="has 5' gene", is_metadata_tag=False)

TYPES = {"Gene": GENE, "Factor": FACTOR, "Fusion": FUSION}


class CIVICGeneGetter(Obo):
    """An ontology representation of CiVIC's gene nomenclature."""

    bioversions_key = ontology = PREFIX
    typedefs = [HAS_3P, HAS_5P]
    root_terms = [GENE.reference, FACTOR.reference, FUSION.reference]

    def iter_terms(self, force: bool = False) -> Iterable[Term]:
        """Iterate over gene terms for CiVIC."""
        yield from (GENE, FACTOR, FUSION)
        yield from get_terms(self._version_or_raise, force=force)


def get_terms(version: str, force: bool = False) -> Iterable[Term]:
    """Get CIVIC terms."""
    dt = datetime.datetime.strptime(version, "%Y-%m-%d")
    # version is like 01-Feb-2024
    dt2 = datetime.datetime.strftime(dt, "%d-%b-%Y")
    url = f"https://civicdb.org/downloads/{dt2}/{dt2}-GeneSummaries.tsv"
    df = ensure_df(prefix=PREFIX, url=url, sep="\t", force=force, dtype=str, version=version)
    for (
        identifier,
        _,
        type,
        name,
        aliases,
        description,
        _last_review_date,
        _flag,
        entrez_id,
        ncit_id,
        _5p_status,
        _3p_status,
        five_p_id,
        _5p_name,
        _5p_ncbigene,
        three_p_id,
        _3p_name,
        _3p_ncbigene,
    ) in df.values:
        term = Term(
            reference=Reference(prefix=PREFIX, identifier=identifier, name=name),
            definition=description if pd.notna(description) else None,
        )
        term.append_parent(TYPES[type])
        if pd.notna(entrez_id):
            term.append_exact_match(Reference(prefix="ncbigene", identifier=entrez_id))
        if pd.notna(ncit_id):
            term.append_exact_match(Reference(prefix="ncit", identifier=ncit_id))
        if pd.notna(aliases):
            for alias in aliases.split(","):
                if alias != name:
                    term.append_synonym(alias.strip())
        if pd.notna(five_p_id):
            term.append_relationship(
                HAS_5P, Reference(prefix=PREFIX, identifier=five_p_id, name=_5p_name)
            )
        if pd.notna(three_p_id):
            term.append_relationship(
                HAS_3P, Reference(prefix=PREFIX, identifier=three_p_id, name=_3p_name)
            )

        yield term


if __name__ == "__main__":
    CIVICGeneGetter.cli()
