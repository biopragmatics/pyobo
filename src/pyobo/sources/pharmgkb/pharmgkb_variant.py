"""An ontology representation of PharmGKB variants."""

from collections.abc import Iterable

import pandas as pd

from pyobo import Obo, Reference, Term, TypeDef
from pyobo.sources.pharmgkb.utils import download_pharmgkb_tsv, split

__all__ = [
    "PharmGKBVariantGetter",
]

PREFIX = "pharmgkb.variant"
URL = "https://api.pharmgkb.org/v1/download/file/data/variants.zip"


HAS_GENE_ASSOCIATION = TypeDef.default(
    PREFIX, "hasGeneAssociation", name="has gene association", is_metadata_tag=True
)


class PharmGKBVariantGetter(Obo):
    """An ontology representation of PharmGKB variants."""

    ontology = bioversions_key = PREFIX
    typedefs = [HAS_GENE_ASSOCIATION]
    dynamic_version = True

    def iter_terms(self, force: bool = False) -> Iterable[Term]:
        """Iterate over terms in the ontology."""
        return iter_terms(force=force)


def iter_terms(force: bool = False) -> Iterable[Term]:
    """Iterate over terms.

    :param force: Should the data be re-downloaded

    :yields: Terms

    1. Variant ID = The PharmGKB identifier for this variant
    2. Variant Name = The PharmGKB name for this variant
    3. Gene IDs = The PharmGKB identifiers for genes associated with this variant
    4. Gene Symbols = The HGNC symbols for genes associated with this variant
    5. Location = The location of this variation on a reference sequence (either RefSeq
       or GenBank), if available. HGVS format when applicable
    6. Variant Annotation count = The count of Variant Annotations done on this variant
    7. Clinical Annotation count = The count of all Clinical Annotations done on this
       variant
    8. Level 1/2 Clinical Annotation count = The count of Level 1 or Level 2 ("top")
       Clinical Annotations done on this variant
    9. Guideline Annotation count = The count of Dosing Guideline Annotations of which
       this variant is a part
    10. Label Annotation count = The count of Drug Label Annotations in which this
        variant is mentioned
    11. Synonym
    """
    df = download_pharmgkb_tsv(PREFIX, url=URL, inner="variants.tsv", force=force)

    for _, row in df.iterrows():
        identifier = row["Variant ID"]
        if pd.isna(identifier):
            continue

        term = Term.from_triple(PREFIX, identifier=str(identifier))

        dbsnp_id = row["Variant Name"]
        if pd.notna(dbsnp_id):
            term.append_exact_match(Reference(prefix="dbsnp", identifier=dbsnp_id))

        for gene_id, gene_name in zip(
            split(row, "Gene IDs"), split(row, "Gene Symbols"), strict=False
        ):
            gene_ref = Reference(prefix="pharmgkb.gene", identifier=gene_id, name=gene_name)
            term.annotate_object(HAS_GENE_ASSOCIATION, gene_ref)

        # TODO location, like NC_000003.12:183917980

        yield term


if __name__ == "__main__":
    PharmGKBVariantGetter.cli()
