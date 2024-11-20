"""Convert GTDB taxonomy to OBO format."""

import logging
from collections.abc import Iterable

import pandas as pd
from tqdm.auto import tqdm

from pyobo.struct import Obo, Reference, Term
from pyobo.struct.typedef import has_taxonomy_rank
from pyobo.utils.path import ensure_path

__all__ = [
    "GTDBGetter",
]

PREFIX = "gtdb"
LEVEL_ORDER = ["d__", "p__", "c__", "o__", "f__", "g__", "s__"]

#: A mapping from GTDB prefixes to TAXRANK ranks
LEVEL_TO_TAXRANK = {
    "d__": Reference(prefix="TAXRANK", identifier="0000037", name="domain"),
    "p__": Reference(prefix="TAXRANK", identifier="0000001", name="phylum"),
    "c__": Reference(prefix="TAXRANK", identifier="0000002", name="class"),
    "o__": Reference(prefix="TAXRANK", identifier="0000003", name="order"),
    "f__": Reference(prefix="TAXRANK", identifier="0000004", name="family"),
    "g__": Reference(prefix="TAXRANK", identifier="0000005", name="genus"),
    "s__": Reference(prefix="TAXRANK", identifier="0000006", name="species"),
}

GTDB_AR_URL = "https://data.gtdb.ecogenomic.org/releases/latest/ar53_metadata.tsv.gz"
GTDB_BAC_URL = "https://data.gtdb.ecogenomic.org/releases/latest/bac120_metadata.tsv.gz"

logger = logging.getLogger(__name__)


class GTDBGetter(Obo):
    """An ontology representation of the GTDB taxonomy."""

    ontology = bioversions_key = PREFIX
    typedefs = [has_taxonomy_rank]

    def iter_terms(self, force: bool = False) -> Iterable[Term]:
        """Iterate over terms in the ontology."""
        return iter_terms(version=self._version_or_raise, force=force)


def _parse_gtdb_taxonomy(tax_string: str) -> list[tuple[str, str]]:
    """Parse GTDB taxonomy string into (level, name) tuples."""
    taxa = []
    parts = [p.strip() for p in tax_string.split(";") if p.strip()]

    for part in parts:
        if len(part) < 4 or "__" not in part:
            logger.warning(f"Malformed taxon string: {part}")
            continue
        level = part[:3]
        name = part[3:].strip()
        if level in LEVEL_ORDER and name:
            taxa.append((level, name))
        else:
            logger.warning(f"Invalid taxonomic level or name in part: {part}")
    return taxa


def iter_terms(version: str, force: bool = False) -> Iterable[Term]:
    """Iterate over GTDB terms."""
    ar_path = ensure_path(PREFIX, url=GTDB_AR_URL, version=version, force=force)
    bac_path = ensure_path(PREFIX, url=GTDB_BAC_URL, version=version, force=force)
    columns = ["gtdb_taxonomy", "ncbi_taxid"]
    for path_name, path in [
        ("ar", ar_path),
        ("bac", bac_path),
    ]:
        df = pd.read_csv(path, sep="\t", dtype=str)
        for tax_string, ncbitaxon_id in tqdm(
            df[columns].values, desc=f"[{PREFIX}] processing {path_name}", unit_scale=True
        ):
            yield from _process_row(tax_string, ncbitaxon_id)


def _process_row(tax_string, ncbitaxon_id) -> Iterable[Term]:
    if not isinstance(tax_string, str):
        logger.warning(f"Invalid taxonomy string: {tax_string}")
        return None

    taxa = _parse_gtdb_taxonomy(tax_string)
    if not taxa:
        logger.warning(f"No valid taxa found in: {tax_string}")
        return None

    parent_reference = None
    for level, name in taxa:
        identifier = f"{level}{name.replace(' ', '_')}"
        term = Term(
            reference=Reference(prefix=PREFIX, identifier=identifier, name=name),
        )
        if taxrank_reference := LEVEL_TO_TAXRANK.get(level):
            term.append_property(has_taxonomy_rank, taxrank_reference)

        if parent_reference:
            term.append_parent(parent_reference)
        if ncbitaxon_id and level == "s__":
            term.append_xref(Reference(prefix="ncbitaxon", identifier=ncbitaxon_id))

        yield term
        parent_reference = term.reference


if __name__ == "__main__":
    GTDBGetter().write_default(write_obo=True, force=True)
