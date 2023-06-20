# -*- coding: utf-8 -*-

"""Swisslipids."""

from typing import Iterable

import pandas as pd
from tqdm.auto import tqdm

from pyobo import Obo, SynonymTypeDef, Term
from pyobo.utils.path import ensure_df

__all__ = [
    "SLMGetter",
]

PREFIX = "slm"
COLUMNS = [
    "Lipid ID",
    "Level",
    "Name",
    "Abbreviation*",
    "Synonyms*",
    "Lipid class*",
    "Parent",
    "Components*",
    "SMILES (pH7.3)",
    "InChI (pH7.3)",
    "InChI key (pH7.3)",
    # "Formula (pH7.3)", "Charge (pH7.3)", "Mass (pH7.3)",
    # "Exact Mass (neutral form)", "Exact m/z of [M.]+", "Exact m/z of [M+H]+", "Exact m/z of [M+K]+ ",
    # "Exact m/z of [M+Na]+", "Exact m/z of [M+Li]+", "Exact m/z of [M+NH4]+", "Exact m/z of [M-H]-",
    # "Exact m/z of [M+Cl]-", "Exact m/z of [M+OAc]- ",
    "CHEBI",
    "LIPID MAPS",
    "HMDB",
    "PMID",
]

abreviation_type = SynonymTypeDef.from_text("abbreviation")


class SLMGetter(Obo):
    """An ontology representation of SwissLipid's lipid nomenclature."""

    ontology = bioversions_key = PREFIX
    synonym_typedefs = [abreviation_type]

    def iter_terms(self, force: bool = False) -> Iterable[Term]:
        """Iterate over terms in the ontology."""
        return iter_terms(force=force, version=self._version_or_raise)


def get_obo(force: bool = False) -> Obo:
    """Get SwissLipids as OBO."""
    return SLMGetter(force=force)


def iter_terms(version: str, force: bool = False):
    """Iterate over SwissLipids terms."""
    df = ensure_df(
        prefix=PREFIX,
        url="https://www.swisslipids.org/api/file.php?cas=download_files&file=lipids.tsv",
        version=version,
        name="lipids.tsv.gz",
        encoding="cp1252",
        force=force,
    )
    for (
        identifier,
        level,
        name,
        abbreviation,
        synonyms,
        _cls,
        _parent,
        _components,
        smiles,
        inchi,
        inchikey,
        chebi_id,
        lipidmaps_id,
        hmdb_id,
        pmids,
    ) in tqdm(
        df[COLUMNS].values, desc=f"[{PREFIX}] generating terms", unit_scale=True, unit="lipid"
    ):
        if identifier.startswith("SLM:"):
            identifier = identifier[len("SLM:") :]
        else:
            raise ValueError(identifier)
        term = Term.from_triple(PREFIX, identifier, name)
        term.append_property("level", level)
        if pd.notna(abbreviation):
            term.append_synonym(abbreviation, type=abreviation_type)
        if pd.notna(synonyms):
            for synonym in synonyms.split("|"):
                term.append_synonym(synonym.strip())
        if pd.notna(smiles):
            term.append_property("smiles", smiles)
        if pd.notna(inchi) and inchi != "InChI=none":
            if inchi.startswith("InChI="):
                inchi = inchi[len("InChI=") :]
            term.append_property("inchi", inchi)
        if pd.notna(inchikey):
            if inchikey.startswith("InChIKey="):
                inchikey = inchikey[len("InChIKey=") :]
            term.append_property("inchikey", inchikey)
        if pd.notna(chebi_id):
            term.append_xref(("chebi", chebi_id))
        if pd.notna(lipidmaps_id):
            term.append_xref(("lipidmaps", lipidmaps_id))
        if pd.notna(hmdb_id):
            term.append_xref(("hmdb", hmdb_id))
        if pd.notna(pmids):
            for pmid in pmids.split("|"):
                term.append_provenance(("pubmed", pmid))
        # TODO how to handle class, parents, and components?
        yield term


if __name__ == "__main__":
    get_obo().write_default(write_obo=True, use_tqdm=True)
