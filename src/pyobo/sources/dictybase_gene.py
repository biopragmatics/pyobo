"""Converter for dictyBase gene.

Note that normal dictybase idenififers are for sequences
"""

import logging
from collections.abc import Iterable

import pandas as pd
from tqdm.auto import tqdm

from pyobo.struct import Obo, Term, from_species, has_gene_product
from pyobo.utils.path import ensure_df

__all__ = [
    "DictybaseGetter",
]

logger = logging.getLogger(__name__)

PREFIX = "dictybase.gene"
URL = (
    "http://dictybase.org/db/cgi-bin/dictyBase/download/"
    "download.pl?area=general&ID=gene_information.txt"
)
UNIPROT_MAPPING = (
    "http://dictybase.org/db/cgi-bin/dictyBase/download/"
    "download.pl?area=general&ID=DDB-GeneID-UniProt.txt"
)


class DictybaseGetter(Obo):
    """An ontology representation of Dictybase's gene nomenclature."""

    ontology = PREFIX
    dynamic_version = True
    typedefs = [from_species, has_gene_product]

    def iter_terms(self, force: bool = False) -> Iterable[Term]:
        """Iterate over terms in the ontology."""
        return get_terms(force=force)


def get_terms(force: bool = False) -> Iterable[Term]:
    """Get terms."""
    # TODO the mappings file has actually no uniprot at all, and requires text mining
    # DDB ID	DDB_G ID	Name	UniProt ID
    # uniprot_mappings = multisetdict(
    #     ensure_df(PREFIX, url=URL, force=force, name="uniprot_mappings.tsv", usecols=[1, 3]).values
    # )

    terms = ensure_df(PREFIX, url=URL, force=force, name="gene_info.tsv")
    # GENE ID (DDB_G ID)	Gene Name	Synonyms	Gene products
    for identifier, name, synonyms, products in tqdm(terms.values):
        term = Term.from_triple(
            prefix=PREFIX,
            identifier=identifier,
            name=name,
        )
        if products and pd.notna(products) and products != "unknown":
            for synonym in products.split(","):
                term.append_synonym(synonym.strip())
        if synonyms and pd.notna(synonyms):
            for synonym in synonyms.split(","):
                term.append_synonym(synonym.strip())
        # for uniprot_id in uniprot_mappings.get(identifier, []):
        #     if not uniprot_id or pd.isna(uniprot_id) or uniprot_id in {"unknown", "pseudogene"}:
        #         continue
        #     try:
        #         uniprot_ref = Reference(prefix="uniprot", identifier=uniprot_id)
        #     except ValueError:
        #         tqdm.write(f"[dictybase.gene] invalid uniprot ref: {uniprot_id}")
        #     else:
        #         term.append_relationship(has_gene_product, uniprot_ref)

        term.set_species(identifier="44689", name="Dictyostelium discoideum")
        yield term


if __name__ == "__main__":
    DictybaseGetter.cli()
