"""Converter for NPASS."""

import logging
from collections.abc import Iterable

import pandas as pd
from tqdm.auto import tqdm

from ..struct import Obo, Reference, Term
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


def get_df(version: str, force: bool = False) -> pd.DataFrame:
    """Get the NPASS chemical nomenclature."""
    base_url = f"https://bidd.group/NPASS/downloadFiles/NPASSv{version}_download"
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
    for identifier, name, iupac, chembl_id, pubchem_compound_ids, _, _, _, _ in it:
        term = Term.from_triple(
            PREFIX, identifier=identifier, name=name if pd.notna(name) else identifier
        )

        for xref_prefix, xref_id in [
            ("chembl.compound", chembl_id),
            # ("zinc", zinc_id),
        ]:
            if pd.notna(xref_id):
                term.append_xref(Reference(prefix=xref_prefix, identifier=xref_id))

        # TODO check that the first is always the parent compound?
        if pd.notna(pubchem_compound_ids):
            pubchem_compound_ids = [
                zz
                for xx in pubchem_compound_ids.split(";")
                for yy in xx.strip().split(",")
                if (zz := yy.strip())
            ]
            if len(pubchem_compound_ids) > 1:
                logger.debug("multiple cids for %s: %s", identifier, pubchem_compound_ids)
            for pubchem_compound_id in pubchem_compound_ids:
                term.append_xref(
                    Reference(prefix="pubchem.compound", identifier=pubchem_compound_id.strip())
                )

        for synonym in [iupac]:
            if pd.notna(synonym):
                term.append_synonym(synonym)

        yield term


if __name__ == "__main__":
    NPASSGetter.cli()
