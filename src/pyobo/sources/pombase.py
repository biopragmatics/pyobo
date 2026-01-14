"""Converter for PomBase."""

import logging
from collections import defaultdict
from collections.abc import Iterable

import pandas as pd
from tqdm.auto import tqdm

import pyobo
from pyobo import Reference, TypeDef
from pyobo.resources.so import get_so_name
from pyobo.struct import Obo, Term, from_species, has_gene_product, orthologous
from pyobo.utils.path import ensure_df

__all__ = [
    "PomBaseGetter",
]

logger = logging.getLogger(__name__)

PREFIX = "pombase"
GENE_NAMES_URL = "https://www.pombase.org/data/names_and_identifiers/gene_IDs_names_products.tsv"
ORTHOLOGS_URL = "https://www.pombase.org/data/orthologs/human-orthologs.txt.gz"
CHROMOSOME = TypeDef.default(PREFIX, "chromosome", is_metadata_tag=True)


class PomBaseGetter(Obo):
    """An ontology representation of PomBase's fission yeast gene nomenclature."""

    ontology = bioversions_key = PREFIX
    typedefs = [from_species, has_gene_product, orthologous, CHROMOSOME]

    def iter_terms(self, force: bool = False) -> Iterable[Term]:
        """Iterate over terms in the ontology."""
        return get_terms(force=force, version=self._version_or_raise)


#: A mapping from PomBase gene type to sequence ontology terms
POMBASE_TO_SO = {
    # None: "0000704",  # gene,
    "gene_type": "0000704",  # unannotated
    "protein coding gene": "0001217",
    "pseudogene": "0000336",
    "tRNA gene": "0001272",
    "ncRNA gene": "0001263",
    "snRNA gene": "0001268",
    "snoRNA gene": "0001267",
    "rRNA gene": "0001637",
    "lncRNA gene": "0002127",
    "sncRNA gene": "0002342",
}


def get_terms(version: str, force: bool = False) -> Iterable[Term]:
    """Get terms."""
    orthologs_df = ensure_df(PREFIX, url=ORTHOLOGS_URL, force=force, header=None, version=version)
    identifier_to_hgnc_ids = defaultdict(set)
    hgnc_symbol_to_id = pyobo.get_name_id_mapping("hgnc")
    for identifier, hgnc_symbols in orthologs_df.values:
        if hgnc_symbols == "NONE":
            continue
        for hgnc_symbol in hgnc_symbols.split("|"):
            hgnc_id = hgnc_symbol_to_id.get(hgnc_symbol)
            if hgnc_id is not None:
                identifier_to_hgnc_ids[identifier].add(hgnc_id)

    df = ensure_df(PREFIX, url=GENE_NAMES_URL, force=force, version=version)
    so = {
        gtype: Reference(
            prefix="SO", identifier=POMBASE_TO_SO[gtype], name=get_so_name(POMBASE_TO_SO[gtype])
        )
        for gtype in sorted(df[df.columns[6]].unique())
    }
    for _, reference in sorted(so.items()):
        yield Term(reference=reference)
    for identifier, _, symbol, chromosome, name, uniprot_id, gtype, synonyms in tqdm(
        df.values, unit_scale=True
    ):
        if pd.isna(identifier):
            continue
        term = Term.from_triple(
            prefix=PREFIX,
            identifier=identifier,
            name=symbol if pd.notna(symbol) else None,
            definition=name if pd.notna(name) else None,
        )
        term.annotate_string(CHROMOSOME, chromosome[len("chromosome_") :])
        term.append_parent(so[gtype])
        term.set_species(identifier="4896", name="Schizosaccharomyces pombe")
        for hgnc_id in identifier_to_hgnc_ids.get(identifier, []):
            term.annotate_object(orthologous, Reference(prefix="hgnc", identifier=hgnc_id))
        if uniprot_id and pd.notna(uniprot_id):
            term.annotate_object(
                has_gene_product, Reference(prefix="uniprot", identifier=uniprot_id)
            )
        if synonyms and pd.notna(synonyms):
            for synonym in synonyms.split(","):
                term.append_synonym(synonym.strip())
        yield term


if __name__ == "__main__":
    PomBaseGetter.cli()
