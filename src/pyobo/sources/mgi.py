# -*- coding: utf-8 -*-

"""Converter for MGI."""

from collections import defaultdict
from typing import Iterable

import pandas as pd
from tqdm import tqdm

from ..struct import Obo, Reference, Synonym, Term, from_species
from ..utils.path import ensure_df

PREFIX = "mgi"
MARKERS_URL = "http://www.informatics.jax.org/downloads/reports/MRK_List2.rpt"
ENTREZ_XREFS_URL = "http://www.informatics.jax.org/downloads/reports/MGI_EntrezGene.rpt"
ENSEMBL_XREFS_URL = "http://www.informatics.jax.org/downloads/reports/MRK_ENSEMBL.rpt"


def get_obo() -> Obo:
    """Get MGI as OBO."""
    return Obo(
        ontology=PREFIX,
        name="Mouse Genome Database",
        iter_terms=get_terms,
        typedefs=[from_species],
        auto_generated_by=f"bio2obo:{PREFIX}",
    )


COLUMNS = ["MGI Accession ID", "Marker Symbol", "Marker Name"]


def get_ensembl_df() -> pd.DataFrame:
    """Get the Ensembl mappings dataframe."""
    return ensure_df(
        PREFIX,
        url=ENSEMBL_XREFS_URL,
        sep="\t",
        names=[
            "mgi_id",
            "symbol",
            "name",
            "position",
            "chromosome",
            "ensembl_accession_id",
            "ensembl_transcript_id",
            "ensembl_protein_id",
            "feature_type",
            "start",
            "end",
            "strand",
            "biotypes",
        ],
    )


def get_entrez_df() -> pd.DataFrame:
    """Get the Entrez mappings dataframe."""
    return ensure_df(
        PREFIX,
        url=ENTREZ_XREFS_URL,
        sep="\t",
        names=[
            "mgi_id",
            "symbol",
            "status",
            "name",
            "position",
            "chromosome",
            "Type",
            "Secondary Accession IDs",
            "entrez_id",
            "synonyms",
            "Features",
            "start",
            "end",
            "strand",
            "biotypes",
        ],
        dtype={
            "entrez_id": str,
        },
    )


def get_terms() -> Iterable[Term]:
    """Get the MGI terms."""
    df = ensure_df(PREFIX, url=MARKERS_URL, sep="\t")

    entrez_df = get_entrez_df()
    mgi_to_entrez_id, mgi_to_synonyms = {}, {}
    for mgi_id, synonyms, entrez_id in entrez_df[["mgi_id", "synonyms", "entrez_id"]].values:
        mgi_id = mgi_id[len("MGI:") :]
        if synonyms and pd.notna(synonyms):
            mgi_to_synonyms[mgi_id] = synonyms.split("|")
        if entrez_id and pd.notna(entrez_id):
            mgi_to_entrez_id[mgi_id] = entrez_id

    ensembl_df = get_ensembl_df()
    # ensembl_df.to_csv('test.tsv', sep='\t', index=False)
    mgi_to_ensemble_ids = defaultdict(list)
    ensembl_columns = [
        "mgi_id",
        "ensembl_accession_id",
        "ensembl_transcript_id",
        "ensembl_protein_id",
    ]
    ensembl_it = ensembl_df[ensembl_columns].values
    for mgi_id, ensemble_accession_id, ensemble_transcript_ids, ensemble_protein_ids in ensembl_it:
        mgi_id = mgi_id[len("MGI:") :]
        if ensemble_accession_id and pd.notna(ensemble_accession_id):
            mgi_to_ensemble_ids[mgi_id].append(ensemble_accession_id)
        if ensemble_transcript_ids and pd.notna(ensemble_transcript_ids):
            for ensemble_transcript_id in ensemble_transcript_ids.split():
                mgi_to_ensemble_ids[mgi_id].append(ensemble_transcript_id)
        if ensemble_protein_ids and pd.notna(ensemble_protein_ids):
            for ensemble_protein_id in ensemble_protein_ids.split():
                mgi_to_ensemble_ids[mgi_id].append(ensemble_protein_id)

    for identifier, name, definition in tqdm(
        df[COLUMNS].values, total=len(df.index), desc=f"Mapping {PREFIX}"
    ):
        identifier = identifier[len("MGI:") :]

        synonyms = []
        if identifier in mgi_to_synonyms:
            for synonym in mgi_to_synonyms[identifier]:
                synonyms.append(Synonym(name=synonym))

        xrefs = []
        if identifier in mgi_to_entrez_id:
            xrefs.append(Reference(prefix="ncbigene", identifier=mgi_to_entrez_id[identifier]))
        if identifier in mgi_to_ensemble_ids:
            for ensembl_id in mgi_to_ensemble_ids[identifier]:
                xrefs.append(Reference(prefix="ensembl", identifier=ensembl_id))

        term = Term(
            reference=Reference(prefix=PREFIX, identifier=identifier, name=name),
            definition=definition,
            xrefs=xrefs,
            synonyms=synonyms,
        )
        term.set_species(identifier="10090", name="Mus musculus")
        yield term


if __name__ == "__main__":
    get_obo().write_default()
