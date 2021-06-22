# -*- coding: utf-8 -*-

"""Converter for PathBank."""

import logging
from collections import defaultdict
from typing import Iterable, Mapping, Set

import pandas as pd
from tqdm import tqdm

from ..struct import Obo, Reference, Term
from ..struct.typedef import has_part
from ..utils.path import ensure_df

logger = logging.getLogger(__name__)

PREFIX = "pathbank"

PATHWAY_URL = "https://pathbank.org/downloads/pathbank_all_pathways.csv.zip"
PATHWAY_COLUMNS = [
    "SMPDB ID",
    "PW ID",
    "Name",
    "Subject",
    "Description",
]

PROTEINS_URL = "https://pathbank.org/downloads/pathbank_all_proteins.csv.zip"
PROTEINS_COLUMNS = [
    "PathBank ID",
    "Pathway Name",
    "Pathway Subject",
    "Species",
    "Uniprot ID",
    "Protein Name",
    "HMDBP ID",
    "DrugBank ID",
    "GenBank ID",
    "Gene Name",
    "Locus",
]

METABOLITE_URL = "https://pathbank.org/downloads/pathbank_all_metabolites.csv.zip"
METABOLITE_COLUMNS = [
    "PathBank ID",
    "Pathway Name",
    "Pathway Subject",
    "Species",
    "Metabolite ID",
    "Metabolite Name",
    "HMDB ID",
    "KEGG ID",
    "ChEBI ID",
    "DrugBank ID",
    "CAS",
    "Formula",
    "IUPAC",
    "SMILES",
    "InChI",
    "InChI Key",
]


def get_obo() -> Obo:
    """Get PathBank as OBO."""
    return Obo(
        ontology=PREFIX,
        name="PathBank",
        typedefs=[has_part],
        iter_terms=iter_terms,
        auto_generated_by=f"bio2obo:{PREFIX}",
    )


def get_proteins_df() -> pd.DataFrame:
    """Get the proteins dataframe."""
    proteins_df = ensure_df(
        PREFIX,
        url=PROTEINS_URL,
        sep=",",
        usecols=["PathBank ID", "Uniprot ID"],
    )
    proteins_df = proteins_df[proteins_df["Uniprot ID"].notna()]
    proteins_df = proteins_df[proteins_df["Uniprot ID"] != "Unknown"]
    proteins_df["Uniprot ID"] = proteins_df["Uniprot ID"].map(str.strip)
    return proteins_df


def get_protein_mapping() -> Mapping[str, Set[Reference]]:
    """Make the protein mapping."""
    proteins_df = get_proteins_df()
    smpdb_id_to_proteins = defaultdict(set)
    for pathway_id, protein_id in tqdm(
        proteins_df.values, desc=f"[{PREFIX}] mapping proteins", unit_scale=True
    ):
        # TODO get protein names
        smpdb_id_to_proteins[pathway_id].add(Reference(prefix="uniprot", identifier=protein_id))
    return smpdb_id_to_proteins


def get_metabolite_df() -> pd.DataFrame:
    """Get the metabolites dataframe."""
    return ensure_df(
        PREFIX,
        url=METABOLITE_URL,
        sep=",",
        usecols=["PathBank ID", "Metabolite ID", "Metabolite Name"],
    )


def get_metabolite_mapping() -> Mapping[str, Set[Reference]]:
    """Make the metabolite mapping."""
    metabolites_df = get_metabolite_df()
    smpdb_id_to_metabolites = defaultdict(set)
    it = tqdm(metabolites_df.values, desc=f"[{PREFIX}] mapping metabolites", unit_scale=True)
    for pathway_id, metabolite_id, metabolite_name in it:
        smpdb_id_to_metabolites[pathway_id].add(
            Reference(
                prefix=PREFIX,
                identifier=metabolite_id,
                name=metabolite_name,
            )
        )
    return smpdb_id_to_metabolites


def iter_terms() -> Iterable[Term]:
    """Get PathBank's terms."""
    smpdb_id_to_proteins = get_protein_mapping()
    smpdb_id_to_metabolites = get_metabolite_mapping()

    pathways_df = ensure_df(PREFIX, url=PATHWAY_URL, sep=",")
    it = tqdm(pathways_df.values, total=len(pathways_df.index), desc=f"mapping {PREFIX}")
    for smpdb_id, pathbank_id, name, subject, _description in it:
        reference = Reference(prefix=PREFIX, identifier=pathbank_id, name=name)
        term = Term(
            reference=reference,
            # definition=description.replace('\n', ' '),
            xrefs=[Reference(prefix="smpdb", identifier=smpdb_id)],
        )
        term.append_parent(
            Reference(
                prefix=PREFIX,
                identifier=subject.lower().replace(" ", "_"),
                name=subject,
            )
        )
        term.extend_relationship(has_part, smpdb_id_to_proteins[smpdb_id])
        term.extend_relationship(has_part, smpdb_id_to_metabolites[smpdb_id])
        yield term


if __name__ == "__main__":
    get_obo().write_default()
