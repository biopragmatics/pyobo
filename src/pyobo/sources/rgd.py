"""Converter for RGD."""

import logging
from collections.abc import Iterable
from typing import Optional

import pandas as pd
from tqdm.auto import tqdm

from pyobo.struct import (
    Obo,
    Reference,
    Synonym,
    SynonymTypeDef,
    Term,
    from_species,
    has_gene_product,
    transcribes_to,
)
from pyobo.utils.path import ensure_df

logger = logging.getLogger(__name__)
PREFIX = "rgd"

old_symbol_type = SynonymTypeDef.from_text("old_symbol")
old_name_type = SynonymTypeDef.from_text("old_name")

# NOTE unigene id was discontinue in January 18th, 2021 dump

GENES_URL = "https://download.rgd.mcw.edu/data_release/GENES_RAT.txt"
GENES_HEADER = [
    "GENE_RGD_ID",
    "SYMBOL",
    "NAME",
    "GENE_DESC",
    "CHROMOSOME_CELERA",
    "CHROMOSOME_[oldAssembly#] chromosome for the old reference assembly",
    "CHROMOSOME_[newAssembly#] chromosome for the current reference assembly",
    "FISH_BAND",
    "START_POS_CELERA",
    "STOP_POS_CELERA",
    "STRAND_CELERA",
    "START_POS_[oldAssembly#]",
    "STOP_POS_[oldAssembly#]",
    "STRAND_[oldAssembly#]",
    "START_POS_[newAssembly#]",
    "STOP_POS_[newAssembly#]",
    "STRAND_[newAssembly#]",
    "CURATED_REF_RGD_ID",
    "CURATED_REF_PUBMED_ID",
    "UNCURATED_PUBMED_ID",
    "NCBI_GENE_ID",
    "UNIPROT_ID",
    "UNCURATED_REF_MEDLINE_ID",
    "GENBANK_NUCLEOTIDE",
    "TIGR_ID",
    "GENBANK_PROTEIN",
    "SSLP_RGD_ID",
    "SSLP_SYMBOL",
    "OLD_SYMBOL",
    "OLD_NAME",
    "QTL_RGD_ID",
    "QTL_SYMBOL",
    "NOMENCLATURE_STATUS",
    "SPLICE_RGD_ID",
    "SPLICE_SYMBOL",
    "GENE_TYPE",
    "ENSEMBL_ID",
]


class RGDGetter(Obo):
    """An ontology representation of RGD's rat gene nomenclature."""

    bioversions_key = ontology = PREFIX
    typedefs = [from_species, transcribes_to, has_gene_product]
    synonym_typedefs = [old_name_type, old_symbol_type]

    def iter_terms(self, force: bool = False) -> Iterable[Term]:
        """Iterate over terms in the ontology."""
        return get_terms(force=force, version=self._version_or_raise)


def get_obo(force: bool = False) -> Obo:
    """Get RGD as OBO."""
    return RGDGetter(force=force)


namespace_to_column = [
    ("ensembl", "ENSEMBL_ID"),
    ("uniprot", "UNIPROT_ID"),
    ("ncbigene", "NCBI_GENE_ID"),
]


def get_terms(force: bool = False, version: Optional[str] = None) -> Iterable[Term]:
    """Get RGD terms."""
    df = ensure_df(
        PREFIX,
        url=GENES_URL,
        sep="\t",
        header=0,
        comment="#",
        dtype=str,
        force=force,
        version=version,
        quoting=3,
        on_bad_lines="skip",
    )
    for _, row in tqdm(
        df.iterrows(), total=len(df.index), desc=f"Mapping {PREFIX}", unit_scale=True
    ):
        if pd.notna(row["NAME"]):
            definition = row["NAME"]
        elif pd.notna(row["GENE_DESC"]):
            definition = row["GENE_DESC"]
        else:
            definition = None

        term = Term(
            reference=Reference(prefix=PREFIX, identifier=row["GENE_RGD_ID"], name=row["SYMBOL"]),
            definition=definition,
        )
        old_names = row["OLD_NAME"]
        if old_names and pd.notna(old_names):
            for old_name in old_names.split(";"):
                term.append_synonym(Synonym(name=old_name, type=old_name_type))
        old_symbols = row["OLD_SYMBOL"]
        if old_symbols and pd.notna(old_symbols):
            for old_symbol in old_symbols.split(";"):
                term.append_synonym(Synonym(name=old_symbol, type=old_symbol_type))
        for prefix, key in namespace_to_column:
            xref_ids = str(row[key])
            if xref_ids and pd.notna(xref_ids):
                for xref_id in xref_ids.split(";"):
                    if xref_id == "nan":
                        continue
                    if prefix == "uniprot":
                        term.append_relationship(
                            has_gene_product, Reference(prefix=prefix, identifier=xref_id)
                        )
                    elif prefix == "ensembl":
                        if xref_id.startswith("ENSMUSG") or xref_id.startswith("ENSRNOG"):
                            # second one is reverse strand
                            term.append_xref(Reference(prefix=prefix, identifier=xref_id))
                        elif xref_id.startswith("ENSMUST"):
                            term.append_relationship(
                                transcribes_to, Reference(prefix=prefix, identifier=xref_id)
                            )
                        elif xref_id.startswith("ENSMUSP"):
                            term.append_relationship(
                                has_gene_product, Reference(prefix=prefix, identifier=xref_id)
                            )
                        else:
                            logger.warning("[%s] unhandled xref ensembl:%s", PREFIX, xref_id)
                    else:
                        term.append_xref(Reference(prefix=prefix, identifier=xref_id))

        pubmed_ids = row["CURATED_REF_PUBMED_ID"]
        if pubmed_ids and pd.notna(pubmed_ids):
            for pubmed_id in str(pubmed_ids).split(";"):
                term.append_provenance(Reference(prefix="pubmed", identifier=pubmed_id))

        term.set_species(identifier="10116", name="Rattus norvegicus")
        yield term


if __name__ == "__main__":
    RGDGetter.cli()
