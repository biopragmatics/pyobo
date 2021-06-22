# -*- coding: utf-8 -*-

"""Converter for Reactome."""

import logging
from typing import Iterable

import bioversions
import pandas as pd
from tqdm import tqdm

from ..api import get_name_id_mapping
from ..constants import SPECIES_REMAPPING
from ..struct import Obo, Reference, Term, from_species, has_part
from ..utils.io import multidict
from ..utils.path import ensure_df

logger = logging.getLogger(__name__)

PREFIX = "reactome"


# TODO alt ids https://reactome.org/download/current/reactome_stable_ids.txt


def get_obo() -> Obo:
    """Get Reactome OBO."""
    version = bioversions.get_version("reactome")
    return Obo(
        ontology=PREFIX,
        name="Reactome",
        iter_terms=iter_terms,
        iter_terms_kwargs=dict(version=version),
        typedefs=[from_species, has_part],
        data_version=version,
        auto_generated_by=f"bio2obo:{PREFIX}",
    )


def iter_terms(version: str) -> Iterable[Term]:
    """Iterate Reactome terms."""
    ncbitaxon_name_to_id = get_name_id_mapping("ncbitaxon")

    provenance_url = f"https://reactome.org/download/{version}/ReactionPMIDS.txt"
    provenance_df = ensure_df(PREFIX, url=provenance_url, header=None, version=version)
    provenance_d = multidict(provenance_df.values)

    pathway_names_url = f"https://reactome.org/download/{version}/ReactomePathways.txt"
    df = ensure_df(
        PREFIX,
        url=pathway_names_url,
        header=None,
        names=["reactome_id", "name", "species"],
        version=version,
    )
    df["species"] = df["species"].map(lambda x: SPECIES_REMAPPING.get(x) or x)
    df["taxonomy_id"] = df["species"].map(ncbitaxon_name_to_id.get)

    terms = {}
    it = tqdm(df.values, total=len(df.index), desc=f"mapping {PREFIX}")
    for reactome_id, name, species_name, taxonomy_id in it:
        terms[reactome_id] = term = Term(
            reference=Reference(prefix=PREFIX, identifier=reactome_id, name=name),
            provenance=[
                Reference(prefix="pubmed", identifier=pmid)
                for pmid in provenance_d.get(reactome_id, [])
            ],
        )
        if not taxonomy_id or pd.isna(taxonomy_id):
            raise ValueError(f"unmapped species: {species_name}")

        term.set_species(identifier=taxonomy_id, name=species_name)

    pathways_hierarchy_url = f"https://reactome.org/download/{version}/ReactomePathwaysRelation.txt"
    hierarchy_df = ensure_df(PREFIX, url=pathways_hierarchy_url, header=None, version=version)
    for parent_id, child_id in hierarchy_df.values:
        terms[child_id].append_parent(terms[parent_id])

    uniprot_pathway_url = f"https://reactome.org/download/{version}/UniProt2Reactome_All_Levels.txt"
    uniprot_pathway_df = ensure_df(
        PREFIX, url=uniprot_pathway_url, header=None, usecols=[0, 1], version=version
    )
    for uniprot_id, reactome_id in tqdm(uniprot_pathway_df.values, total=len(uniprot_pathway_df)):
        terms[reactome_id].append_relationship(has_part, Reference("uniprot", uniprot_id))

    chebi_pathway_url = f"https://reactome.org/download/{version}/ChEBI2Reactome_All_Levels.txt"
    chebi_pathway_df = ensure_df(
        PREFIX, url=chebi_pathway_url, header=None, usecols=[0, 1], version=version
    )
    for chebi_id, reactome_id in tqdm(chebi_pathway_df.values, total=len(chebi_pathway_df)):
        terms[reactome_id].append_relationship(has_part, Reference("chebi", chebi_id))

    # ncbi_pathway_url = f'https://reactome.org/download/{version}/NCBI2Reactome_All_Levels.txt'
    # ncbi_pathway_df = ensure_df(PREFIX, url=ncbi_pathway_url, header=None, usecols=[0, 1], version=version)
    # for ncbigene_id, reactome_id in tqdm(ncbi_pathway_df.values, total=len(ncbi_pathway_df)):
    #     terms[reactome_id].append_relationship(has_part, Reference('ncbigene', ncbigene_id))

    yield from terms.values()


if __name__ == "__main__":
    get_obo().write_default()
