"""Converter for FlyBase Genes."""

import logging
from collections.abc import Iterable, Mapping

import pandas as pd
from tqdm.auto import tqdm

from pyobo import Reference
from pyobo.resources.so import get_so_name
from pyobo.struct import Obo, Term, _parse_str_or_curie_or_uri, from_species, orthologous
from pyobo.utils.io import multisetdict
from pyobo.utils.path import ensure_df

__all__ = [
    "FlyBaseGetter",
]

logger = logging.getLogger(__name__)

BASE_URL = "https://s3ftp.flybase.org/releases"
PREFIX = "flybase"
NAME = "FlyBase"


class FlyBaseGetter(Obo):
    """An ontology representation of FlyBase's gene nomenclature."""

    ontology = bioversions_key = PREFIX
    typedefs = [from_species, orthologous]

    def iter_terms(self, force: bool = False) -> Iterable[Term]:
        """Iterate over terms in the ontology."""
        return get_terms(force=force, version=self._version_or_raise)


def _get_names(version: str, force: bool = False) -> pd.DataFrame:
    url = f"{BASE_URL}/FB{version}/precomputed_files/genes/fbgn_fbtr_fbpp_expanded_fb_{version}.tsv.gz"
    df = ensure_df(
        PREFIX,
        url=url,
        force=force,
        version=version,
        skiprows=4,
        usecols=[0, 1, 2, 3, 4],
        skipfooter=1,
        engine="python",
    )
    return df


def _get_organisms(version: str, force: bool = False) -> Mapping[str, str]:
    """Get mapping from abbreviation column to NCBI taxonomy ID column."""
    url = f"{BASE_URL}/FB{version}/precomputed_files/species/organism_list_fb_{version}.tsv.gz"
    df = ensure_df(
        PREFIX, url=url, force=force, version=version, skiprows=4, header=None, usecols=[2, 4]
    )
    df.dropna(inplace=True)
    return dict(df.values)


def _get_definitions(version: str, force: bool = False) -> Mapping[str, str]:
    url = f"{BASE_URL}/FB{version}/precomputed_files/genes/automated_gene_summaries.tsv.gz"
    df = ensure_df(
        PREFIX, url=url, force=force, version=version, skiprows=2, header=None, usecols=[0, 1]
    )
    return dict(df.values)


def _get_human_orthologs(version: str, force: bool = False) -> Mapping[str, set[str]]:
    url = (
        f"{BASE_URL}/FB{version}/precomputed_files/"
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
    url = f"{BASE_URL}/FB{version}/precomputed_files/synonyms/fb_synonym_fb_{version}.tsv.gz"
    df = ensure_df(PREFIX, url=url, force=force, version=version, skiprows=4, usecols=[0, 2])
    return df  # TODO use this


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
    "mt_LSU_rRNA_gene": None,
}


def get_terms(version: str, force: bool = False) -> Iterable[Term]:
    """Get terms."""
    definitions = _get_definitions(version=version, force=force)
    abbr_to_taxonomy = _get_organisms(version=version, force=force)
    names_df = _get_names(version=version, force=force)
    human_orthologs = _get_human_orthologs(version=version, force=force)
    missing_taxonomies = set()

    so = {}
    for gtype in names_df[names_df.columns[1]].unique():
        so_id = GTYPE_TO_SO.get(gtype)
        if so_id is None:
            logger.warning(
                "FlyBase gene type is missing mapping to Sequence Ontology (SO): %s", gtype
            )
        else:
            so[gtype] = Reference(prefix="SO", identifier=so_id, name=get_so_name(so_id))

    for _, reference in sorted(so.items()):
        yield Term(reference=reference)
    for organism, gtype, identifier, symbol, name in tqdm(
        names_df.values, unit_scale=True, unit="gene", desc="FlyBase genes"
    ):
        term = Term.from_triple(
            prefix=PREFIX,
            identifier=identifier,
            name=symbol if pd.notna(symbol) else None,
            definition=definitions.get(identifier),
        )
        if gtype and pd.notna(gtype) and gtype in so:
            term.append_parent(so[gtype])
        if pd.notna(name):
            term.append_synonym(name)
        for hgnc_curie in human_orthologs.get(identifier, []):
            if not hgnc_curie or pd.isna(hgnc_curie):
                continue
            hgnc_ortholog = _parse_str_or_curie_or_uri(hgnc_curie)
            if hgnc_ortholog is None:
                tqdm.write(f"[{PREFIX}] {identifier} had invalid ortholog: {hgnc_curie}")
            else:
                term.annotate_object(orthologous, hgnc_ortholog)
        taxonomy_id = abbr_to_taxonomy.get(organism)
        if taxonomy_id is not None:
            term.set_species(taxonomy_id)
        elif organism not in missing_taxonomies:
            tqdm.write(f"[{PREFIX}] missing mapping for species abbreviation: {organism}")
            missing_taxonomies.add(organism)
        yield term

    if missing_taxonomies:
        tqdm.write(f"[{PREFIX}] there were {len(missing_taxonomies)} missing taxa in flybase genes")


if __name__ == "__main__":
    FlyBaseGetter.cli()
