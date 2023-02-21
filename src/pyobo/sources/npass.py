# -*- coding: utf-8 -*-

"""Converter for NPASS."""

import logging
from typing import Iterable

import pandas as pd
from tqdm.auto import tqdm

from ..struct import Obo, Reference, Synonym, Term
from ..utils.path import ensure_df

__all__ = [
    "NPASSGetter",
]

logger = logging.getLogger(__name__)

PREFIX = "npass"


# TODO add InChI, InChI-key, and SMILES information from NPASS, if desired
# METADATA_URL = f'{BASE_URL}_naturalProducts_properties.txt'


class NPASSGetter(Obo):
    """An ontology representation of NPASS's chemical nomenclature."""

    ontology = bioversions_key = PREFIX

    def iter_terms(self, force: bool = False) -> Iterable[Term]:
        """Iterate over terms in the ontology."""
        return iter_terms(force=force, version=self._version_or_raise)


def get_obo(force: bool = False) -> Obo:
    """Get NPASS as OBO."""
    return NPASSGetter()


def get_df(version: str, force: bool = False) -> pd.DataFrame:
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
        force=force,
    )


def iter_terms(version: str, force: bool = False) -> Iterable[Term]:
    """Iterate NPASS terms."""
    df = get_df(version=version, force=force)
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
