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


def get_obo(force: bool = False) -> Obo:
    """Get DrugCentral OBO."""
    version = bioversions.get_version(PREFIX)
    return Obo(
        ontology=PREFIX,
        name="DrugCentral",
        data_version=version,
        iter_terms=iter_terms,
        iter_terms_kwargs=dict(version=version, force=force),
        auto_generated_by=f"bio2obo:{PREFIX}",
    )


def iter_terms(version: str, force: bool = False) -> Iterable[Term]:
    """Iterate over DrugCentral terms."""
    df = ensure_df(PREFIX, url=URL, version=version, force=force)
    for smiles, inchi, inchi_key, drugcentral_id, drugcentral_name, cas in df.values:
        if pd.isna(smiles) or pd.isna(inchi) or pd.isna(inchi_key):
            logger.warning("missing data for drugcentral:%s", drugcentral_id)
            continue
        term = Term.from_triple(prefix=PREFIX, identifier=drugcentral_id, name=drugcentral_name)
        term.append_xref(Reference(prefix="inchikey", identifier=inchi_key))
        term.append_property("smiles", smiles)
        term.append_property("inchi", inchi)
        if pd.notna(cas):
            term.append_xref(Reference(prefix="cas", identifier=cas))
        yield term


if __name__ == "__main__":
    get_obo(force=True).write_default(write_obo=True)
