# -*- coding: utf-8 -*-

"""Converter for dictyBase gene.

Note that normal dictybase idenififers are for sequences
"""

import logging
from typing import Iterable

import pandas as pd
from tqdm.auto import tqdm

from pyobo.struct import Obo, Reference, Synonym, Term, from_species, has_gene_product
from pyobo.utils.io import multisetdict
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


def get_obo(force: bool = False) -> Obo:
    """Get dictyBase Gene as OBO."""
    return DictybaseGetter(force=force)


def get_terms(force: bool = False) -> Iterable[Term]:
    """Get terms."""
    # DDB ID	DDB_G ID	Name	UniProt ID
    uniprot_mappings = multisetdict(
        ensure_df(PREFIX, url=URL, force=force, name="uniprot_mappings.tsv", usecols=[1, 3]).values
    )

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
                term.append_synonym(Synonym(synonym.strip()))
        for uniprot_id in uniprot_mappings.get(identifier, []):
            if not uniprot_id or pd.isna(uniprot_id) or uniprot_id not in {"unknown", "pseudogene"}:
                continue
            term.append_relationship(has_gene_product, Reference.auto("uniprot", uniprot_id))

        term.set_species(identifier="44689", name="Dictyostelium discoideum")
        yield term


if __name__ == "__main__":
    DictybaseGetter.cli()
