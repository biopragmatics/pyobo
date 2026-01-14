"""Converter for Entrez."""

import logging
from collections.abc import Iterable, Mapping

import bioregistry
import pandas as pd
from tqdm.auto import tqdm

from ...struct import Obo, Reference, Term, from_species
from ...utils.path import ensure_df

__all__ = [
    "NCBIGeneGetter",
]

logger = logging.getLogger(__name__)

PREFIX = "ncbigene"

SPECIES_CONSORTIUM_MAPPING = {
    "10090": "mgi",  # Mouse
    "10116": "rgd",  # Rat
    "4932": "sgd",  # Yeast
    "7227": "flybase",  # Drosophila
    "9606": "hgnc",  # Human
    "6239": "wormbase",  # C. Elegans
    "7955": "zfin",  # Zebrafish
}

#: All namepace codes (in lowercase) that can map to ncbigene
CONSORTIUM_SPECIES_MAPPING = {
    database_code: taxonomy_id for taxonomy_id, database_code in SPECIES_CONSORTIUM_MAPPING.items()
}

GENE_INFO_URL = "ftp://ftp.ncbi.nlm.nih.gov/gene/DATA/gene_info.gz"
#: Columns for gene_info.gz that are used
GENE_INFO_COLUMNS = [
    "#tax_id",
    "GeneID",
    "Symbol",
    "dbXrefs",
    "description",
    "type_of_gene",
]


def get_ncbigene_ids() -> set[str]:
    """Get the Entrez name mapping."""
    df = _get_ncbigene_subset(["GeneID"])
    return set(df["GeneID"])


def get_ncbigene_id_to_name_mapping() -> Mapping[str, str]:
    """Get the Entrez name mapping."""
    return _get_ncbigene_info_subset(["GeneID", "Symbol"])


def get_ncbigene_id_to_species_mapping() -> Mapping[str, str]:
    """Get the Entrez species mapping."""
    return _get_ncbigene_info_subset(["GeneID", "Symbol"])


def _get_ncbigene_info_subset(usecols) -> Mapping[str, str]:
    df = _get_ncbigene_subset(usecols)
    return dict(df.values)


def _get_ncbigene_subset(usecols: list[str]) -> pd.DataFrame:
    df = ensure_df(
        PREFIX,
        url=GENE_INFO_URL,
        sep="\t",
        na_values=["-", "NEWENTRY"],
        usecols=usecols,
        dtype=str,
    )
    df.dropna(inplace=True)
    if len(usecols) > 1:
        df = df[usecols]
    return df


class NCBIGeneGetter(Obo):
    """An ontology representation of NCBI's Entrez Gene database."""

    ontology = PREFIX
    dynamic_version = True
    typedefs = [from_species]

    def iter_terms(self, force: bool = False) -> Iterable[Term]:
        """Iterate over terms in the ontology."""
        return get_terms(force=force)


def get_gene_info_df(force: bool = False) -> pd.DataFrame:
    """Get the gene info dataframe."""
    return ensure_df(
        PREFIX,
        url=GENE_INFO_URL,
        sep="\t",
        na_values=["-", "NEWENTRY"],
        usecols=GENE_INFO_COLUMNS,
        dtype=str,
        force=force,
    )


def _get_xref_mapping() -> list[str]:
    namespaces: set[str] = set()
    df = get_gene_info_df()
    for xrefs in df[df["dbXrefs"].notna()]["dbXrefs"]:
        for xref in xrefs.split("|"):
            namespaces.add(xref.split(":")[0])
    return sorted(namespaces, key=str.casefold)


# this was retrieved from :func:`_get_xref_mapping`
xref_mapping = {
    "APHIDBASE",
    "ASAP",
    "AnimalQTLdb",
    "ApiDB_CryptoDB",
    "Araport",
    "BEEBASE",
    "BEETLEBASE",
    "BGD",
    "CGNC",
    "ECOCYC",
    "EcoGene",
    "Ensembl",
    "FLYBASE",
    "HGNC",
    "IMGT/GENE-DB",
    "MGI",
    "MIM",
    "NASONIABASE",
    "PseudoCap",
    "RGD",
    "SGD",
    "TAIR",
    "VGNC",
    "VectorBase",
    "WormBase",
    "Xenbase",
    "ZFIN",
    "dictyBase",
    "miRBase",
}
xref_mapping = {x.lower() for x in xref_mapping}


def get_terms(force: bool = False) -> Iterable[Term]:
    """Get Entrez terms.

    :param force: should re-download be forced?

    :yields: terms for each line
    """
    df = get_gene_info_df(force=force)

    it = tqdm(
        df.values, total=len(df.index), desc=f"mapping {PREFIX}", unit_scale=True, unit="gene"
    )
    warning_prefixes = set()
    for tax_id, gene_id, symbol, xref_curies, description, _gene_type in it:
        if pd.isna(symbol):
            continue
        term = Term(
            reference=Reference(prefix=PREFIX, identifier=gene_id, name=symbol),
            definition=description if pd.notna(description) else None,
        )
        term.set_species(identifier=tax_id)
        if pd.notna(xref_curies):
            for xref_curie in xref_curies.split("|"):
                if xref_curie.startswith("EnsemblRapid"):
                    continue
                elif xref_curie.startswith("AllianceGenome"):
                    xref_curie = xref_curie[len("xref_curie") :]
                elif xref_curie.startswith("nome:WB:"):
                    xref_curie = xref_curie[len("nome:") :]
                xref_prefix, xref_id = bioregistry.parse_curie(xref_curie)
                if xref_prefix and xref_id:
                    term.append_xref(Reference(prefix=xref_prefix, identifier=xref_id))
                else:
                    p = xref_curie.split(":")[0]
                    if p not in warning_prefixes:
                        warning_prefixes.add(p)
                        tqdm.write(f"[{PREFIX}] unhandled prefix in xref: {xref_curie}")
        yield term


if __name__ == "__main__":
    NCBIGeneGetter.cli()
