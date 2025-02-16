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

#: A mapping from GTDB prefixes to TAXRANK ranks
LEVEL_TO_TAXRANK = {
    "d": Reference(prefix="TAXRANK", identifier="0000037", name="domain"),
    "p": Reference(prefix="TAXRANK", identifier="0000001", name="phylum"),
    "c": Reference(prefix="TAXRANK", identifier="0000002", name="class"),
    "o": Reference(prefix="TAXRANK", identifier="0000003", name="order"),
    "f": Reference(prefix="TAXRANK", identifier="0000004", name="family"),
    "g": Reference(prefix="TAXRANK", identifier="0000005", name="genus"),
    "s": Reference(prefix="TAXRANK", identifier="0000006", name="species"),
}

#: AR stands for archea
GTDB_AR_URL = "https://data.gtdb.ecogenomic.org/releases/latest/ar53_metadata.tsv.gz"
#: BAC stands for bacteria
GTDB_BAC_URL = "https://data.gtdb.ecogenomic.org/releases/latest/bac120_metadata.tsv.gz"

logger = logging.getLogger(__name__)


class GTDBGetter(Obo):
    """An ontology representation of the GTDB taxonomy."""

    ontology = bioversions_key = PREFIX
    typedefs = [has_taxonomy_rank]
    root_terms = [
        Reference(prefix=PREFIX, identifier="d__Archea", name="Archea"),
        Reference(prefix=PREFIX, identifier="d__Bacteria", name="Bacteria"),
    ]

    def iter_terms(self, force: bool = False) -> Iterable[Term]:
        """Iterate over terms in the ontology."""
        return iter_terms(version=self._version_or_raise, force=force)


def iter_terms(version: str, force: bool = False) -> Iterable[Term]:
    """Iterate over GTDB terms."""
    # Add the taxrank terms so we get nice display in Protege
    for reference in LEVEL_TO_TAXRANK.values():
        yield Term(reference=reference)

    ar_path = ensure_path(PREFIX, url=GTDB_AR_URL, version=version, force=force)
    bac_path = ensure_path(PREFIX, url=GTDB_BAC_URL, version=version, force=force)
    columns = ["gtdb_taxonomy", "ncbi_species_taxid"]
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

    taxa = _parse_tax_string(tax_string)
    if not taxa:
        logger.warning(f"No valid taxa found in: {tax_string}")
        return None

    parent_reference = None
    for level, name in taxa:
        identifier = f"{level}__{name.replace(' ', '_')}"
        term = Term(
            reference=Reference(prefix=PREFIX, identifier=identifier, name=name),
        )
        term.annotate_object(has_taxonomy_rank, LEVEL_TO_TAXRANK[level])

        if parent_reference:
            term.append_parent(parent_reference)
        if ncbitaxon_id and level == "s":
            # if the level is "s", it's a species. There might be multiple
            # mappings to NCBITaxon, so we only use "see also" as the predicate
            term.append_xref(
                Reference(prefix="ncbitaxon", identifier=ncbitaxon_id),
                # TODO @jose use confidence=... keyword here
            )

        yield term
        parent_reference = term.reference


def _parse_tax_string(tax_string: str) -> list[tuple[str, str]]:
    """Parse GTDB taxonomy string into (level, name) tuples."""
    return [
        level_name for part in _split_tax_string(tax_string) if (level_name := _parse_name(part))
    ]


def _split_tax_string(tax_string: str) -> list[str]:
    return [p.strip() for p in tax_string.split(";") if p.strip()]


def _parse_name(part: str) -> tuple[str, str] | None:
    """Parse a GTDB taxonomy identifier.

    :param part: The string
    :returns: A tuple with the level and name, if parsable

    >>> _parse_name("f__Sulfolobaceae")
    ('f', 'Sulfoobaceae')

    The following is malformed because it is missing a double underscore

    >>> _parse_name("f_Sulfolobaceae")

    The following is malformed because it has an invalid taxonomic level

    >>> _parse_name("x__Sulfolobaceae")

    The following is malformed because it's missing a name

    >>> _parse_name("f__")
    """
    if len(part) < 4 or "__" not in part:
        logger.warning(f"Malformed taxon string: {part}")
        return None
    level, delimiter, name = part.partition("__")
    if not delimiter:
        logger.warning(f"Missing double underscore delimiter: {part}")
        return None
    if level not in LEVEL_TO_TAXRANK or not name:
        logger.warning(f"Invalid taxonomic level `{level}` in {part}")
        return None
    if not name:
        logger.warning(f"Missing name: {part}")
        return None
    return level, name


if __name__ == "__main__":
    GTDBGetter().cli()
