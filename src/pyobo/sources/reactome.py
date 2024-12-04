"""Converter for Reactome."""

import logging
from collections import defaultdict
from collections.abc import Iterable, Mapping
from functools import lru_cache

import pandas as pd
from tqdm.auto import tqdm

from ..api import get_id_multirelations_mapping
from ..constants import SPECIES_REMAPPING
from ..resources.ncbitaxon import get_ncbitaxon_id
from ..struct import Obo, Reference, Term, from_species, has_participant
from ..utils.io import multidict
from ..utils.path import ensure_df

__all__ = [
    "ReactomeGetter",
]

logger = logging.getLogger(__name__)

PREFIX = "reactome"


# TODO alt ids https://reactome.org/download/current/reactome_stable_ids.txt


class ReactomeGetter(Obo):
    """An ontology representation of the Reactome pathway database."""

    ontology = bioversions_key = PREFIX
    typedefs = [from_species, has_participant]

    def iter_terms(self, force: bool = False) -> Iterable[Term]:
        """Iterate over terms in the ontology."""
        return iter_terms(version=self._version_or_raise, force=force)


def get_obo(force: bool = False) -> Obo:
    """Get Reactome OBO."""
    return ReactomeGetter(force=force)


def ensure_participant_df(version: str, force: bool = False) -> pd.DataFrame:
    """Get the pathway uniprot participant dataframe."""
    uniprot_pathway_url = f"https://reactome.org/download/{version}/UniProt2Reactome_All_Levels.txt"
    return ensure_df(
        PREFIX, url=uniprot_pathway_url, header=None, usecols=[0, 1], version=version, force=force
    )


def iter_terms(version: str, force: bool = False) -> Iterable[Term]:
    """Iterate Reactome terms."""
    provenance_url = f"https://reactome.org/download/{version}/ReactionPMIDS.txt"
    provenance_df = ensure_df(PREFIX, url=provenance_url, header=None, version=version, force=force)
    provenance_d = multidict(provenance_df.values)

    pathway_names_url = f"https://reactome.org/download/{version}/ReactomePathways.txt"
    df = ensure_df(
        PREFIX,
        url=pathway_names_url,
        header=None,
        names=["reactome_id", "name", "species"],
        version=version,
        force=force,
    )
    df["species"] = df["species"].map(lambda x: SPECIES_REMAPPING.get(x) or x)
    df["taxonomy_id"] = df["species"].map(get_ncbitaxon_id)

    terms = {}
    it = tqdm(
        df.values, total=len(df.index), desc=f"mapping {PREFIX}", unit_scale=True, unit="pathway"
    )
    for reactome_id, name, species_name, taxonomy_id in it:
        terms[reactome_id] = term = Term(
            reference=Reference(prefix=PREFIX, identifier=reactome_id, name=name),
            provenance=[
                Reference(prefix="pubmed", identifier=pubmed_id)
                for pubmed_id in provenance_d.get(reactome_id, [])
            ],
        )
        if not taxonomy_id or pd.isna(taxonomy_id):
            raise ValueError(f"unmapped species: {species_name}")

        term.set_species(identifier=taxonomy_id, name=species_name)

    pathways_hierarchy_url = f"https://reactome.org/download/{version}/ReactomePathwaysRelation.txt"
    hierarchy_df = ensure_df(
        PREFIX, url=pathways_hierarchy_url, header=None, version=version, force=force
    )
    for parent_id, child_id in hierarchy_df.values:
        terms[child_id].append_parent(terms[parent_id])

    uniprot_pathway_df = ensure_participant_df(version=version, force=force)
    for uniprot_id, reactome_id in tqdm(
        uniprot_pathway_df.values,
        total=len(uniprot_pathway_df),
        unit_scale=True,
        unit="pathway-protein",
    ):
        if reactome_id not in terms:
            tqdm.write(f"{reactome_id} appears in uniprot participants file but not pathways file")
            continue

        if "-" in uniprot_id:
            reference = Reference(prefix="uniprot.isoform", identifier=uniprot_id)
        else:
            reference = Reference(prefix="uniprot", identifier=uniprot_id)
        terms[reactome_id].append_relationship(has_participant, reference)

    chebi_pathway_url = f"https://reactome.org/download/{version}/ChEBI2Reactome_All_Levels.txt"
    chebi_pathway_df = ensure_df(
        PREFIX,
        url=chebi_pathway_url,
        header=None,
        usecols=[0, 1],
        version=version,
        force=force,
    )
    for chebi_id, reactome_id in tqdm(
        chebi_pathway_df.values,
        total=len(chebi_pathway_df),
        unit_scale=True,
        unit="pathway-chemical",
    ):
        if reactome_id not in terms:
            tqdm.write(f"{reactome_id} appears in chebi participants file but not pathways file")
            continue
        terms[reactome_id].append_relationship(
            has_participant, Reference(prefix="chebi", identifier=chebi_id)
        )

    # ncbi_pathway_url = f'https://reactome.org/download/{version}/NCBI2Reactome_All_Levels.txt'
    # ncbi_pathway_df = ensure_df(PREFIX, url=ncbi_pathway_url, header=None, usecols=[0, 1], version=version)
    # for ncbigene_id, reactome_id in tqdm(ncbi_pathway_df.values, total=len(ncbi_pathway_df)):
    #     terms[reactome_id].append_relationship(has_part, Reference('ncbigene', ncbigene_id))

    yield from terms.values()


@lru_cache(maxsize=1)
def get_protein_to_pathways() -> Mapping[str, set[str]]:
    """Get a mapping from proteins to the pathways they're in."""
    protein_to_pathways = defaultdict(set)
    x = get_id_multirelations_mapping("reactome", has_participant)
    for reactome_id, proteins in x.items():
        for protein in proteins:
            if protein.prefix != "uniprot":
                continue
            protein_to_pathways[protein.identifier].add(reactome_id)
    return dict(protein_to_pathways)


if __name__ == "__main__":
    ReactomeGetter.cli()
