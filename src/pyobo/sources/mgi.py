"""Converter for MGI."""

import logging
from collections import defaultdict
from collections.abc import Iterable

import pandas as pd
from tqdm.auto import tqdm

from pyobo.struct.typedef import exact_match

from ..struct import (
    Obo,
    Reference,
    Term,
    from_species,
    has_gene_product,
    transcribes_to,
)
from ..utils.path import ensure_df

__all__ = [
    "MGIGetter",
]

logger = logging.getLogger(__name__)

PREFIX = "mgi"
MARKERS_URL = "http://www.informatics.jax.org/downloads/reports/MRK_List2.rpt"
ENTREZ_XREFS_URL = "http://www.informatics.jax.org/downloads/reports/MGI_EntrezGene.rpt"
ENSEMBL_XREFS_URL = "http://www.informatics.jax.org/downloads/reports/MRK_ENSEMBL.rpt"


class MGIGetter(Obo):
    """An ontology representation of MGI's mouse gene nomenclature."""

    ontology = bioversions_key = PREFIX
    typedefs = [from_species, has_gene_product, transcribes_to, exact_match]

    def iter_terms(self, force: bool = False) -> Iterable[Term]:
        """Iterate over terms in the ontology."""
        return get_terms(force=force)


COLUMNS = ["MGI Accession ID", "Marker Symbol", "Marker Name"]


def get_ensembl_df(force: bool = False) -> pd.DataFrame:
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
        force=force,
        dtype=str,
    )


def get_entrez_df(
    force: bool = False,
) -> pd.DataFrame:
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
        dtype=str,
        force=force,
    )


def get_terms(force: bool = False) -> Iterable[Term]:
    """Get the MGI terms."""
    df = ensure_df(PREFIX, url=MARKERS_URL, sep="\t", force=force)

    entrez_df = get_entrez_df(force=force)
    mgi_to_entrez_id, mgi_to_synonyms = {}, {}
    for mgi_curie, synonyms, entrez_id in entrez_df[["mgi_id", "synonyms", "entrez_id"]].values:
        mgi_id = mgi_curie[len("MGI:") :]
        if synonyms and pd.notna(synonyms):
            mgi_to_synonyms[mgi_id] = synonyms.split("|")
        if entrez_id and pd.notna(entrez_id):
            mgi_to_entrez_id[mgi_id] = entrez_id

    ensembl_df = get_ensembl_df(force=force)
    # ensembl_df.to_csv('test.tsv', sep='\t', index=False)
    mgi_to_ensemble_accession_ids = defaultdict(list)
    mgi_to_ensemble_transcript_ids = defaultdict(list)
    mgi_to_ensemble_protein_ids = defaultdict(list)
    ensembl_columns = [
        "mgi_id",
        "ensembl_accession_id",
        "ensembl_transcript_id",
        "ensembl_protein_id",
    ]
    ensembl_it = ensembl_df[ensembl_columns].values
    for (
        mgi_curie,
        ensemble_accession_id,
        ensemble_transcript_ids,
        ensemble_protein_ids,
    ) in ensembl_it:
        mgi_id = mgi_curie[len("MGI:") :]
        if ensemble_accession_id and pd.notna(ensemble_accession_id):
            mgi_to_ensemble_accession_ids[mgi_id].append(ensemble_accession_id)
        if ensemble_transcript_ids and pd.notna(ensemble_transcript_ids):
            for ensemble_transcript_id in ensemble_transcript_ids.split():
                mgi_to_ensemble_transcript_ids[mgi_id].append(ensemble_transcript_id)
        if ensemble_protein_ids and pd.notna(ensemble_protein_ids):
            for ensemble_protein_id in ensemble_protein_ids.split():
                mgi_to_ensemble_protein_ids[mgi_id].append(ensemble_protein_id)

    for mgi_curie, name, definition in tqdm(
        df[COLUMNS].values, total=len(df.index), desc=f"Mapping {PREFIX}", unit_scale=True
    ):
        identifier = mgi_curie[len("MGI:") :]
        term = Term(
            reference=Reference(prefix=PREFIX, identifier=identifier, name=name),
            definition=definition,
        )
        if identifier in mgi_to_synonyms:
            for synonym in mgi_to_synonyms[identifier]:
                term.append_synonym(synonym)
        if identifier in mgi_to_entrez_id:
            term.append_exact_match(
                Reference(prefix="ncbigene", identifier=mgi_to_entrez_id[identifier])
            )
        for ensembl_id in mgi_to_ensemble_accession_ids[identifier]:
            term.append_xref(Reference(prefix="ensembl", identifier=ensembl_id))
        for ensembl_id in mgi_to_ensemble_transcript_ids[identifier]:
            term.append_relationship(
                transcribes_to, Reference(prefix="ensembl", identifier=ensembl_id)
            )
        for ensembl_id in mgi_to_ensemble_protein_ids[identifier]:
            term.append_relationship(
                has_gene_product, Reference(prefix="ensembl", identifier=ensembl_id)
            )
        term.set_species(identifier="10090", name="Mus musculus")
        yield term


if __name__ == "__main__":
    MGIGetter.cli()
