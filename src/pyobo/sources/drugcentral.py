# -*- coding: utf-8 -*-

"""Get DrugCentral as OBO."""

import logging
from typing import Iterable

import pandas as pd

from pyobo.struct import Obo, Reference, Term
from pyobo.utils.path import ensure_df

__all__ = [
    "DrugCentralGetter",
]

logger = logging.getLogger(__name__)

PREFIX = "drugcentral"


class DrugCentralGetter(Obo):
    """An ontology representation of the DrugCentral database."""

    ontology = bioversions_key = PREFIX

    def iter_terms(self, force: bool = False) -> Iterable[Term]:
        """Iterate over terms in the ontology."""
        return iter_terms(version=self._version_or_raise, force=force)


def get_obo(force: bool = False) -> Obo:
    """Get DrugCentral OBO."""
    return DrugCentralGetter(force=force)


def iter_terms(version: str, force: bool = False) -> Iterable[Term]:
    """Iterate over DrugCentral terms."""
    url = f"https://unmtid-shinyapps.net/download/DrugCentral/{version}/structures.smiles.tsv"
    df = ensure_df(PREFIX, url=url, version=version, force=force)
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
    DrugCentralGetter.cli()
