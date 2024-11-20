"""Convert GTDB taxonomy to OBO format."""

from collections.abc import Iterable
import logging
from typing import List, Tuple

import pandas as pd
from bioversions import get_version
from pyobo.struct import Obo, Reference, Term
from pyobo.struct.typedef import is_a
from pyobo.utils.path import ensure_path

__all__ = [
    "GTDBGetter",
]

PREFIX = "gtdb"
LEVEL_ORDER = ['d__', 'p__', 'c__', 'o__', 'f__', 'g__', 's__']
LEVEL_NAMES = {
    'd__': 'domain',
    'p__': 'phylum',
    'c__': 'class', 
    'o__': 'order',
    'f__': 'family',
    'g__': 'genus',
    's__': 'species'
}

GTDB_AR_URL = "https://data.gtdb.ecogenomic.org/releases/latest/ar53_metadata.tsv.gz"
GTDB_BAC_URL = "https://data.gtdb.ecogenomic.org/releases/latest/bac120_metadata.tsv.gz"

logger = logging.getLogger(__name__)

class GTDBGetter(Obo):
    """An ontology representation of the GTDB taxonomy."""
    
    ontology = bioversions_key = PREFIX
    typedefs = [is_a]

    def iter_terms(self, force: bool = False) -> Iterable[Term]:
        """Iterate over terms in the ontology."""
        return iter_terms(version=self._version_or_raise, force=force)


def get_obo(force: bool = False) -> Obo:
    """Get GTDB as OBO."""
    return GTDBGetter(force=force)


def _parse_gtdb_taxonomy(tax_string: str) -> List[Tuple[str, str]]:
    """Parse GTDB taxonomy string into (level, name) tuples."""
    taxa = []
    parts = [p.strip() for p in tax_string.split(';') if p.strip()]

    for part in parts:
        if len(part) < 4 or '__' not in part:
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

    for path in [ar_path, bac_path]:
        df = pd.read_csv(path, sep='\t', dtype=str)
        
        for _, row in df.iterrows():
            tax_string = row.get('gtdb_taxonomy')
            ncbi_taxid = row.get('ncbi_taxid')

            if not isinstance(tax_string, str):
                logger.warning(f"Invalid taxonomy string: {tax_string}")
                continue

            taxa = _parse_gtdb_taxonomy(tax_string)
            if not taxa:
                logger.warning(f"No valid taxa found in: {tax_string}")
                continue

            parent_id = None
            for level, name in taxa:
                identifier = f"{level}{name.replace(' ', '_')}"
                term = Term(
                    reference=Reference(prefix=PREFIX, identifier=identifier, name=name),
                    definition=f"{name} is a taxon at the {LEVEL_NAMES.get(level, 'unknown')} level in the GTDB taxonomy."
                )

                if parent_id:
                    term.append_parent(Reference(prefix=PREFIX, identifier=parent_id))
                if ncbi_taxid and level == 's__':
                    term.append_xref(Reference(prefix="ncbitaxon", identifier=ncbi_taxid))

                yield term
                parent_id = identifier


if __name__ == "__main__":
    GTDBGetter().write_default()