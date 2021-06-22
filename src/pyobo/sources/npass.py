# -*- coding: utf-8 -*-

"""Converter for NPASS."""

import logging
from typing import Iterable

import bioversions
import pandas as pd
from tqdm import tqdm

from ..struct import Obo, Reference, Synonym, Term
from ..utils.path import ensure_df

logger = logging.getLogger(__name__)

PREFIX = "npass"
# TODO add InChI, InChI-key, and SMILES information from NPASS, if desired
# METADATA_URL = f'{BASE_URL}_naturalProducts_properties.txt'


def get_obo() -> Obo:
    """Get NPASS as OBO."""
    version = bioversions.get_version("npass")
    return Obo(
        ontology=PREFIX,
        name="Natural Products Activity and Species Source Database",
        iter_terms=iter_terms,
        iter_terms_kwargs=dict(version=version),
        auto_generated_by=f"bio2obo:{PREFIX}",
        pattern=r"NPC\d+",
    )


def get_df(version: str) -> pd.DataFrame:
    """Get the NPASS chemical nomenclature."""
    base_url = f"http://bidd.group/NPASS/downloadFiles/NPASSv{version}_download"
    url = f"{base_url}_naturalProducts_generalInfo.txt"
    return ensure_df(
        PREFIX,
        url=url,
        version=version,
        dtype=str,
        encoding="ISO-8859-1",
        na_values={"NA", "n.a.", "nan"},
    )


def iter_terms(version: str) -> Iterable[Term]:
    """Iterate NPASS terms."""
    df = get_df(version=version)
    it = tqdm(df.values, total=len(df.index), desc=f"mapping {PREFIX}")
    for identifier, name, iupac, chembl_id, pubchem_compound_ids, zinc_id in it:
        xrefs = [
            Reference(prefix=xref_prefix, identifier=xref_id)
            for xref_prefix, xref_id in [
                ("chembl", chembl_id),
                ("zinc", zinc_id),
            ]
            if pd.notna(xref_id)
        ]

        # TODO check that the first is always the parent compound?
        if pd.notna(pubchem_compound_ids):
            pubchem_compound_ids = pubchem_compound_ids.split(";")
            if len(pubchem_compound_ids) > 1:
                logger.warning("multiple cids for %s: %s", identifier, pubchem_compound_ids)
            pubchem_compound_id = pubchem_compound_ids[0]
            xrefs.append(Reference(prefix="pubchem.compound", identifier=pubchem_compound_id))

        yield Term(
            # TODO look up name from pubchem?
            reference=Reference(
                PREFIX, identifier=identifier, name=name if pd.notna(name) else identifier
            ),
            xrefs=xrefs,
            synonyms=[
                Synonym(name=name)
                for name in [
                    iupac,
                ]
                if pd.notna(name)
            ],
        )


if __name__ == "__main__":
    get_obo().write_default()
