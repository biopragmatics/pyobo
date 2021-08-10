# -*- coding: utf-8 -*-

"""Swisslipids."""

import datetime

from pyobo import Obo, SynonymTypeDef, Term
from pyobo.utils.path import ensure_df
from tqdm import tqdm

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
    "Formula (pH7.3)",
    "Charge (pH7.3)",
    "Mass (pH7.3)",
    # "Exact Mass (neutral form)", "Exact m/z of [M.]+", "Exact m/z of [M+H]+", "Exact m/z of [M+K]+ ",
    # "Exact m/z of [M+Na]+", "Exact m/z of [M+Li]+", "Exact m/z of [M+NH4]+", "Exact m/z of [M-H]-",
    # "Exact m/z of [M+Cl]-", "Exact m/z of [M+OAc]- ",
    "CHEBI",
    "LIPID MAPS",
    "HMDB",
    "PMID",
]

abreviation_type = SynonymTypeDef(id="abbreviation", name="Abbreviation")


def get_obo() -> Obo:
    """Get SwissLipids as OBO."""
    version = get_version()

    return Obo(
        ontology=PREFIX,
        name="SwissLipids",
        data_version=version,
        auto_generated_by=f"bio2obo:{PREFIX}",
        iter_terms=iter_terms,
        iter_terms_kwargs=dict(version=version),
    )


def iter_terms(version: str):
    df = ensure_df(
        prefix=PREFIX,
        url="https://www.swisslipids.org/api/file.php?cas=download_files&file=lipids.tsv",
        version=version,
        name="lipids.tsv.gz",
    )

    for (
        identifier,
        level,
        name,
        abbreviation,
        synonyms,
        cls,
        parent,
        components,
        smiles,
        inchi,
        inchikey,
        chebi_id,
        lipidmaps_id,
        hmdb_id,
        pmids,
    ) in tqdm(df[COLUMNS].values):
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
                inchi = inchi[len("InChI=")]
            term.append_property("inchi", inchi)
        if pd.notna(inchikey):
            if inchikey.startswith("InChIKey="):
                inchikey = inchikey[len("InChIKey=")]
            term.append_property("inchikey", inchikey)
        if pd.notna(chebi_id):
            term.append_xref(("chebi", chebi_id))
        if pd.notna(lipidmaps_id):
            term.append_xref(("lipidmaps", lipidmaps_id))
        if pd.notna(hmdb_id):
            term.append_xref(("hmdb", hmdb_id))
        if pd.notna(pmids):
            for pmid in pmids.split("|"):
                term.provenance.append(("pubmed", pmid))
        # TODO how to handle class, parents, and components?
        yield term


import requests


def get_version():
    res = requests.get("https://www.swisslipids.org/api/downloadData").json()
    record = next(record for record in res if record["file"] == "lipids.tsv")
    # August 10 2021
    return datetime.datetime.strptime(record["date"], "%B %d %Y").strftime("%Y-%m-%d")


if __name__ == "__main__":

    for _, _t in zip(range(15), iter_terms(get_version())):
        print(_t)
