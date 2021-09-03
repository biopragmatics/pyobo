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


def get_obo() -> Obo:
    """Get CGNC as OBO."""
    return Obo(
        iter_terms=get_terms,
        name="CGNC",
        ontology=PREFIX,
        typedefs=[from_species],
        auto_generated_by=f"bio2obo:{PREFIX}",
    )


def get_terms() -> Iterable[Term]:
    """Get CGNC terms."""
    df = ensure_df(PREFIX, url=URL, name=f"{PREFIX}.tsv")
    for cgnc_id, entrez_id, ensembl_id, symbol, name, synonyms, _, _ in df.values:
        if pd.isna(cgnc_id):
            logger.warning("CGNC ID is none")
            continue

        try:
            int(cgnc_id)
        except ValueError:
            logger.warning("CGNC ID is not int-like: %s", cgnc_id)
            continue

        term = Term(
            reference=Reference(
                prefix=PREFIX,
                identifier=cgnc_id,
                name=symbol if pd.notna(symbol) else None,
            ),
            definition=name if pd.notna(name) else None,
        )
        term.set_species(identifier="9031", name="Gallus gallus")
        if entrez_id and pd.notna(entrez_id):
            term.append_xref(Reference(prefix="ncbigene", identifier=entrez_id))
        if ensembl_id and pd.notna(ensembl_id):
            term.append_xref(Reference(prefix="ensembl", identifier=ensembl_id))
        if synonyms and pd.notna(synonyms):
            for synonym in synonyms.split("|"):
                synonym = synonym.strip()
                if not synonym:
                    continue
                term.append_synonym(synonym)
        yield term


@click.command()
@verbose_option
def _main():
    obo = get_obo()
    obo.write_default(force=True, write_obonet=True, write_obo=True)


if __name__ == "__main__":
    _main()
