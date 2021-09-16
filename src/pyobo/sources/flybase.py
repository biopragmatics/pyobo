# -*- coding: utf-8 -*-

"""Converter for FlyBase Genes."""

import logging
from typing import Iterable, Mapping, Optional, Set

import click
import pandas as pd
from more_click import verbose_option
from tqdm import tqdm

from pyobo import Reference
from pyobo.struct import Obo, Term, from_species, orthologous
from pyobo.utils.io import multisetdict
from pyobo.utils.path import ensure_df

logger = logging.getLogger(__name__)

BASE_URL = "http://ftp.flybase.net/releases"
PREFIX = "flybase"
NAME = "FlyBase"


def _get_version(version: Optional[str] = None) -> str:
    if version is not None:
        return version
    import bioversions

    return bioversions.get_version("flybase")


def _get_names(version: Optional[str] = None, force: bool = False) -> pd.DataFrame:
    version = _get_version(version)
    url = f"{BASE_URL}/FB{version}/precomputed_files/genes/fbgn_fbtr_fbpp_expanded_fb_{version}.tsv.gz"
    df = ensure_df(
        PREFIX,
        url=url,
        force=force,
        version=version,
        skiprows=4,
        usecols=[0, 1, 2, 3, 4],
        skipfooter=1,
    )
    return df


def _get_organisms(version: Optional[str] = None, force: bool = False) -> Mapping[str, str]:
    """Get mapping from abbreviation column to NCBI taxonomy ID column."""
    version = _get_version(version)
    url = f"http://ftp.flybase.net/releases/FB{version}/precomputed_files/species/organism_list_fb_{version}.tsv.gz"
    df = ensure_df(
        PREFIX, url=url, force=force, version=version, skiprows=4, header=None, usecols=[2, 4]
    )
    df.dropna(inplace=True)
    return dict(df.values)


def _get_definitions(version: Optional[str] = None, force: bool = False) -> Mapping[str, str]:
    version = _get_version(version)
    url = f"http://ftp.flybase.net/releases/FB{version}/precomputed_files/genes/automated_gene_summaries.tsv.gz"
    df = ensure_df(
        PREFIX, url=url, force=force, version=version, skiprows=2, header=None, usecols=[0, 1]
    )
    return dict(df.values)


def _get_human_orthologs(
    version: Optional[str] = None, force: bool = False
) -> Mapping[str, Set[str]]:
    version = _get_version(version)
    url = (
        f"http://ftp.flybase.net/releases/FB{version}/precomputed_files/"
        f"orthologs/dmel_human_orthologs_disease_fb_{version}.tsv.gz"
    )
    df = ensure_df(
        PREFIX,
        url=url,
        force=force,
        version=version,
        skiprows=2,
        header=None,
        usecols=[0, 2],
        names=["flybase_id", "hgnc_id"],
    )
    return multisetdict(df.values)


def _get_synonyms(version, force):
    version = _get_version(version)
    url = f"http://ftp.flybase.net/releases/FB{version}/precomputed_files/synonyms/fb_synonym_fb_{version}.tsv.gz"
    df = ensure_df(PREFIX, url=url, force=force, version=version, skiprows=4, usecols=[0, 2])
    return df  # TODO use this


def get_obo(version: Optional[str] = None, force: bool = False) -> Obo:
    """Get OBO."""
    version = _get_version(version)
    return Obo(
        iter_terms=get_terms,
        iter_terms_kwargs=dict(force=force, version=version),
        name=NAME,
        ontology=PREFIX,
        typedefs=[from_species, orthologous],
        auto_generated_by=f"bio2obo:{PREFIX}",
        data_version=version,
    )


GTYPE_TO_SO = {
    "SRP_RNA_gene": "0001269",
    "protein_coding_gene": "0001217",
    "pseudogene": "0000336",
    "lncRNA_gene": "0002127",
    "snRNA_gene": "0001268",
    "antisense_lncRNA_gene": "0002182",
    "tRNA_gene": "0001272",
    "rRNA_gene": "0001637",
    "snoRNA_gene": "0001267",
    "RNase_P_RNA_gene": "0001639",
    "rRNA_5S_gene": "0002238",
    "ncRNA_gene": "0001263",
    "RNase_MRP_RNA_gene": "0001640",
    "rRNA_18S_gene": "0002236",
    "rRNA_5_8S_gene": "0002240",
    "miRNA_gene": "0001265",
    "rRNA_28S_gene": "0002239",
}


def get_terms(version: Optional[str] = None, force: bool = False) -> Iterable[Term]:
    """Get terms."""
    version = _get_version(version)
    definitions = _get_definitions(version=version, force=force)
    abbr_to_taxonomy = _get_organisms(version=version, force=force)
    names_df = _get_names(version=version, force=force)
    human_orthologs = _get_human_orthologs(version=version, force=force)
    missing_taxonomies = set()

    so = {
        gtype: Reference.auto("SO", GTYPE_TO_SO[gtype])
        for gtype in names_df[names_df.columns[1]].unique()
    }
    for _, reference in sorted(so.items()):
        yield Term(reference=reference)
    for organism, gtype, identifier, symbol, name in tqdm(names_df.values):
        term = Term.from_triple(
            prefix=PREFIX,
            identifier=identifier,
            name=symbol,
            definition=definitions.get(identifier),
        )
        if gtype and pd.notna(gtype):
            term.append_parent(so[gtype])
        if pd.notna(name):
            term.append_synonym(name)
        for hgnc_curie in human_orthologs.get(identifier, []):
            if not hgnc_curie or pd.isna(hgnc_curie):
                continue
            term.append_relationship(orthologous, Reference.from_curie(hgnc_curie, auto=True))
        taxonomy_id = abbr_to_taxonomy.get(organism)
        if taxonomy_id is not None:
            term.append_relationship(from_species, Reference.auto("ncbitaxon", taxonomy_id))
        elif organism not in missing_taxonomies:
            tqdm.write(f"missing mapping for species abbreviation: {organism}")
            missing_taxonomies.add(organism)
        yield term

    if missing_taxonomies:
        tqdm.write(f"there were {len(missing_taxonomies)} missing taxa in flybase genes")


@click.command()
@verbose_option
def _main():
    obo = get_obo(force=True)
    obo.write_default(force=True, write_obo=True, write_obograph=True)


if __name__ == "__main__":
    _main()
