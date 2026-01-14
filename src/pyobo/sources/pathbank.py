"""Converter for PathBank."""

from __future__ import annotations

import logging
from collections import defaultdict
from collections.abc import Iterable, Mapping
from itertools import chain

import pandas as pd
from tqdm.auto import tqdm

from ..struct import Obo, Reference, Term
from ..struct.typedef import has_category, has_participant
from ..utils.path import ensure_df

__all__ = [
    "PathBankGetter",
]

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


class PathBankGetter(Obo):
    """An ontology representation of PathBank's pathway nomenclature."""

    ontology = bioversions_key = PREFIX
    typedefs = [has_participant, has_category]

    def iter_terms(self, force: bool = False) -> Iterable[Term]:
        """Iterate over terms in the ontology."""
        return iter_terms(force=force, version=self._version_or_raise)


def get_proteins_df(version: str, force: bool = False) -> pd.DataFrame:
    """Get the proteins dataframe."""
    proteins_df = ensure_df(
        PREFIX,
        url=PROTEINS_URL,
        sep=",",
        usecols=["PathBank ID", "Uniprot ID"],
        version=version,
        force=force,
    )
    proteins_df = proteins_df[proteins_df["Uniprot ID"].notna()]
    proteins_df = proteins_df[proteins_df["Uniprot ID"] != "Unknown"]
    proteins_df["Uniprot ID"] = proteins_df["Uniprot ID"].map(str.strip)
    return proteins_df


def get_protein_mapping(version: str, force: bool = False) -> Mapping[str, set[Reference]]:
    """Make the protein mapping."""
    proteins_df = get_proteins_df(version=version, force=force)
    smpdb_id_to_proteins = defaultdict(set)
    for pathway_id, protein_id in tqdm(
        proteins_df.values, desc=f"[{PREFIX}] mapping proteins", unit_scale=True
    ):
        try:
            if "-" in protein_id:
                reference = Reference(prefix="uniprot.isoform", identifier=protein_id)
            else:
                reference = Reference(prefix="uniprot", identifier=protein_id)
        except ValueError:
            tqdm.write(f"[pathbank] invalid uniprot identifier: {protein_id}")
        else:
            smpdb_id_to_proteins[pathway_id].add(reference)
    return smpdb_id_to_proteins


def get_metabolite_df(version: str, force: bool = False) -> pd.DataFrame:
    """Get the metabolites dataframe."""
    df = ensure_df(
        PREFIX,
        url=METABOLITE_URL,
        sep=",",
        usecols=["PathBank ID", "ChEBI ID"],
        force=force,
        version=version,
    )
    df = df[df["ChEBI ID"].notna()]
    return df


def get_metabolite_mapping(version: str, force: bool = False) -> Mapping[str, set[Reference]]:
    """Make the metabolite mapping."""
    metabolites_df = get_metabolite_df(version=version, force=force)
    smpdb_id_to_metabolites = defaultdict(set)
    it = tqdm(metabolites_df.values, desc=f"[{PREFIX}] mapping metabolites", unit_scale=True)
    for pathway_id, metabolite_id in it:
        reference = Reference(prefix="chebi", identifier=metabolite_id.strip())
        smpdb_id_to_metabolites[pathway_id].add(reference)
    return smpdb_id_to_metabolites


def _clean_description(description: str) -> str | None:
    """Clean the description."""
    if pd.isna(description) or not description:
        return None
    parts = [part.strip() for part in description.strip().splitlines()]
    return " ".join(parts)


def iter_terms(version: str, force: bool = False) -> Iterable[Term]:
    """Get PathBank's terms."""
    smpdb_id_to_proteins = get_protein_mapping(version=version, force=force)
    smpdb_id_to_metabolites = get_metabolite_mapping(version=version, force=force)

    pathways_df = ensure_df(PREFIX, url=PATHWAY_URL, sep=",", version=version, force=force)
    it = tqdm(pathways_df.values, total=len(pathways_df.index), desc=f"mapping {PREFIX}")
    for smpdb_id, pathbank_id, name, subject, _description in it:
        reference = Reference(prefix=PREFIX, identifier=pathbank_id, name=name)
        term = Term(
            reference=reference,
            # TODO use _clean_description(description) to add a description,
            #  but there are weird parser errors
        )
        term.append_exact_match(Reference(prefix="smpdb", identifier=smpdb_id))
        term.annotate_string(has_category, subject.lower().replace(" ", "_"))
        for participant in chain(smpdb_id_to_proteins[smpdb_id], smpdb_id_to_metabolites[smpdb_id]):
            term.append_relationship(has_participant, participant)
        yield term


if __name__ == "__main__":
    PathBankGetter.cli()
