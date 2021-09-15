# -*- coding: utf-8 -*-

"""Converter for CGNC."""

import logging
from typing import Iterable

import click
import pandas as pd
from more_click import verbose_option

from pyobo.struct import Obo, Reference, Term, from_species
from pyobo.utils.path import ensure_df

PREFIX = "cgnc"
URL = "http://birdgenenames.org/cgnc/downloads.jsp?file=standard"

logger = logging.getLogger(__name__)


def get_obo(force: bool = False) -> Obo:
    """Get CGNC as OBO."""
    return Obo(
        iter_terms=get_terms,
        iter_terms_kwargs=dict(force=force),
        name="CGNC",
        ontology=PREFIX,
        typedefs=[from_species],
        auto_generated_by=f"bio2obo:{PREFIX}",
    )


HEADER = [
    "cgnc_id",
    "ncbigene_id",
    "ensembl_id",
    "name",
    "synonym_1",
    "synonym_2",
    "curation status",
    "last edit date",
]


def get_terms(force: bool = False) -> Iterable[Term]:
    """Get CGNC terms."""
    df = ensure_df(PREFIX, url=URL, name=f"{PREFIX}.tsv", force=force, header=0, names=HEADER)
    for i, (cgnc_id, entrez_id, ensembl_id, name, synonym_1, synoynm_2, _, _) in enumerate(
        df.values
    ):
        if pd.isna(cgnc_id):
            logger.warning(f"row {i} CGNC ID is none")
            continue

        try:
            int(cgnc_id)
        except ValueError:
            logger.warning(f"row {i} CGNC ID is not int-like: {cgnc_id}")
            continue

        term = Term.from_triple(
            prefix=PREFIX,
            identifier=cgnc_id,
            name=name,
        )
        term.set_species(identifier="9031", name="Gallus gallus")
        if entrez_id and pd.notna(entrez_id):
            term.append_xref(Reference(prefix="ncbigene", identifier=entrez_id))
        if pd.notna(ensembl_id):
            term.append_xref(Reference(prefix="ensembl", identifier=ensembl_id))
        if synonym_1 and pd.notna(synonym_1):
            term.append_synonym(synonym_1)
        if synoynm_2 and pd.notna(synoynm_2):
            term.append_synonym(synoynm_2)
        yield term


@click.command()
@verbose_option
def _main():
    obo = get_obo(force=False)
    obo.write_default(force=True, write_obonet=True, write_obo=True)


if __name__ == "__main__":
    _main()
