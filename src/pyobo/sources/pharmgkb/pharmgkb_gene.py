"""An ontology representation of PharmGKB genes."""

from collections.abc import Iterable

import pandas as pd

from pyobo import Obo, Reference, Term
from pyobo.sources.pharmgkb.utils import download_pharmgkb_tsv, parse_xrefs, split

__all__ = [
    "PharmGKBGeneGetter",
]

PREFIX = "pharmgkb.gene"
URL = "https://api.pharmgkb.org/v1/download/file/data/genes.zip"


class PharmGKBGeneGetter(Obo):
    """An ontology representation of PharmGKB genes."""

    ontology = bioversions_key = PREFIX
    dynamic_version = True

    def iter_terms(self, force: bool = False) -> Iterable[Term]:
        """Iterate over terms in the ontology."""
        return iter_terms(force=force)


def iter_terms(force: bool = False) -> Iterable[Term]:
    """Iterate over terms.

    :param force: Should the data be re-downloaded

    :yields: Terms

    1. PharmGKB Accession Id = Identifier assigned to this gene by PharmGKB
    2. NCBI Gene ID = Identifier assigned to this gene by NCBI
    3. HGNC ID = Identifier assigned to this gene by HGNC
    4. Ensembl Id = Identifier assigned to this gene by Ensembl
    5. Name = Canonical name for this gene (by HGNC)
    6. Symbol = Canonical name for this gene (by HGNC)
    7. Alternate Names = Other known names for this gene, comma-separated
    8. Alternate Symbols = Other known symbols for this gene, comma-separated
    9. Is VIP = "Yes" if PharmGKB has written a VIP annotation for this gene, "No"
       otherwise
    10. Has Variant Annotation = "Yes" if PharmGKB has written at least one variant
        annotation for this gene, "No" otherwise
    11. Cross-references = References to other resources in the form "resource:id",
        comma-separated
    12. Has CPIC Dosing Guideline = "Yes" if PharmGKB has annotated a CPIC guideline for
        this gene, "No" otherwise
    13. Chromosome = The chromosome this gene is on, in the form "chr##"
    14. Chromosomal Start - GRCh37 = Where this gene starts on the chromosomal sequence
        for NCBI GRCh37
    15. Chromosomal Stop - GRCh37 = Where this gene stops on the chromosomal sequence
        for NCBI GRCh37
    16. Chromosomal Start - GRCh38 = Where this gene starts on the chromosomal sequence
        for NCBI GRCh38
    17. Chromosomal Stop - GRCh38 = Where this gene stops on the chromosomal sequence
        for NCBI GRCh38
    """
    df = download_pharmgkb_tsv(PREFIX, url=URL, inner="genes.tsv", force=force)

    skip_xrefs = {"ncbigene", "hgnc", "ensembl", "GeneCard"}
    for _, row in df.iterrows():
        identifier = row["PharmGKB Accession Id"]
        if pd.isna(identifier):
            continue

        term = Term.from_triple(PREFIX, identifier=str(identifier), name=row["Name"])

        ncbigene_ids = list(split(row, "NCBI Gene ID"))
        if len(ncbigene_ids) == 1:
            term.append_exact_match(Reference(prefix="ncbigene", identifier=ncbigene_ids[0]))
        else:
            for ncbigene_id in ncbigene_ids:
                term.append_xref(Reference(prefix="ncbigene", identifier=ncbigene_id))

        hgnc_ids = list(split(row, "HGNC ID"))
        if len(hgnc_ids) == 1:
            term.append_exact_match(Reference(prefix="hgnc", identifier=hgnc_ids[0]))
        else:
            for hgnc_id in hgnc_ids:
                term.append_xref(Reference(prefix="hgnc", identifier=hgnc_id))

        for ensembl_id in split(row, "Ensembl Id"):
            term.append_xref(Reference(prefix="ensembl", identifier=ensembl_id))

        for synonym in split(row, "Alternate Names"):
            synonym = synonym.strip('"')
            term.append_synonym(synonym)

        # TODO symbol synonym type
        if pd.notna(row["Symbol"]):
            term.append_synonym(row["Symbol"])
        for synonym in split(row, "Alternate Symbols"):
            term.append_synonym(synonym)

        for xref in parse_xrefs(term, row):
            if xref.prefix in skip_xrefs:
                continue
            term.append_xref(xref)

        yield term


if __name__ == "__main__":
    PharmGKBGeneGetter.cli()
