# -*- coding: utf-8 -*-

"""Converter for Entrez."""

import logging
from typing import Iterable, Mapping

import pandas as pd
from tqdm import tqdm

from ..api import get_id_name_mapping
from ..struct import Obo, Reference, Term, from_species
from ..utils.path import ensure_df

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
#: Columns fro gene_info.gz that are used
GENE_INFO_COLUMNS = [
    "#tax_id",
    "GeneID",
    "Symbol",
    "dbXrefs",
    "description",
    "type_of_gene",
]


def get_ncbigene_id_to_name_mapping() -> Mapping[str, str]:
    """Get the Entrez name mapping."""
    return _get_ncbigene_info_subset(["GeneID", "Symbol"])


def get_ncbigene_id_to_species_mapping() -> Mapping[str, str]:
    """Get the Entrez species mapping."""
    return _get_ncbigene_info_subset(["GeneID", "Symbol"])


def _get_ncbigene_info_subset(usecols) -> Mapping[str, str]:
    df = ensure_df(
        PREFIX,
        url=GENE_INFO_URL,
        sep="\t",
        na_values=["-", "NEWENTRY"],
        usecols=usecols,
        dtype=str,
    )
    df.dropna(inplace=True)
    return dict(df[usecols].values)


def get_obo() -> Obo:
    """Get Entrez as OBO."""
    return Obo(
        ontology=PREFIX,
        name="Entrez Gene",
        iter_terms=get_terms,
        typedefs=[from_species],
        auto_generated_by=f"bio2obo:{PREFIX}",
    )


def get_gene_info_df() -> pd.DataFrame:
    """Get the gene info dataframe."""
    return ensure_df(
        PREFIX,
        url=GENE_INFO_URL,
        sep="\t",
        na_values=["-", "NEWENTRY"],
        usecols=GENE_INFO_COLUMNS,
        dtype={"#tax_id": str, "GeneID": str},
    )


"""xref_mapping was obtained from:

namespaces = set()
for xrefs in df[df['dbXrefs'].notna()]['dbXrefs']:
    for xref in xrefs.split('|'):
        namespaces.add(xref.split(':')[0])

print('namespaces:')
print(*sorted(namespaces), sep='\n')
"""

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


def get_terms() -> Iterable[Term]:
    """Get Entrez terms."""
    df = get_gene_info_df()

    taxonomy_id_to_name = get_id_name_mapping("ncbitaxon")

    it = tqdm(df.values, total=len(df.index), desc=f"mapping {PREFIX}")
    for tax_id, gene_id, symbol, dbxrfs, description, _gene_type in it:
        if pd.isna(symbol):
            continue
        try:
            tax_name = taxonomy_id_to_name[tax_id]
        except KeyError:
            logger.warning(f"Could not look up tax_id={tax_id}")
            tax_name = None

        xrefs = []
        if pd.notna(dbxrfs):
            for xref in dbxrfs.split("|"):
                xref_ns, xref_id = xref.split(":", 1)
                xref_ns = xref_ns.lower()
                xrefs.append(Reference(prefix=xref_ns, identifier=xref_id))

        term = Term(
            reference=Reference(prefix=PREFIX, identifier=gene_id, name=symbol),
            definition=description,
            xrefs=xrefs,
        )
        term.set_species(identifier=tax_id, name=tax_name)
        yield term


if __name__ == "__main__":
    get_obo().write_default()
