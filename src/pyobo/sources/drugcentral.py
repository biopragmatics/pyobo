# -*- coding: utf-8 -*-

"""Get DrugCentral as OBO."""

import logging
from typing import Iterable

import bioversions
import pandas as pd

from pyobo.struct import Obo, Reference, Term
from pyobo.utils.path import ensure_df

logger = logging.getLogger(__name__)

PREFIX = "drugcentral"
URL = "http://unmtid-shinyapps.net/download/structures.smiles.tsv"


def get_obo() -> Obo:
    """Get DrugCentral OBO."""
    version = bioversions.get_version(PREFIX)
    return Obo(
        ontology=PREFIX,
        name="DrugCentral",
        data_version=version,
        iter_terms=iter_terms,
        iter_terms_kwargs=dict(version=version),
        auto_generated_by=f"bio2obo:{PREFIX}",
    )


def iter_terms(version: str) -> Iterable[Term]:
    """Iterate over DrugCentral terms."""
    df = ensure_df(PREFIX, url=URL, version=version)
    for smiles, inchi, inchi_key, drugcentral_id, drugcentral_name, cas in df.values:
        if pd.isna(smiles) or pd.isna(inchi) or pd.isna(inchi_key):
            logger.warning("missing data for drugcentral:%s", drugcentral_id)
            continue
        xrefs = [
            Reference(prefix="smiles", identifier=smiles),
            Reference(prefix="inchi", identifier=inchi),
            Reference(prefix="inchikey", identifier=inchi_key),
        ]

        if pd.notna(cas):
            xrefs.append(Reference(prefix="cas", identifier=cas))

        yield Term(
            reference=Reference(prefix=PREFIX, identifier=drugcentral_id, name=drugcentral_name),
            xrefs=xrefs,
        )


if __name__ == "__main__":
    get_obo().write_default()
