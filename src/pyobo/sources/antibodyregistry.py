"""Converter for the Antibody Registry.

TODO use API https://www.antibodyregistry.org/api/antibodies?page=1&size=100
"""

import logging
from collections.abc import Iterable, Mapping

import pandas as pd
from bioregistry.utils import removeprefix
from tqdm.auto import tqdm

from pyobo import Obo, Reference, Term
from pyobo.api.utils import get_version
from pyobo.struct.typedef import has_citation
from pyobo.utils.path import ensure_df

__all__ = [
    "AntibodyRegistryGetter",
]

logger = logging.getLogger(__name__)

PREFIX = "antibodyregistry"
URL = "http://antibodyregistry.org/php/fileHandler.php"
CHUNKSIZE = 20_000


def get_chunks(*, force: bool = False, version: str | None = None) -> pd.DataFrame:
    """Get the BioGRID identifiers mapping dataframe."""
    if version is None:
        version = get_version(PREFIX)
    df = ensure_df(
        PREFIX,
        url=URL,
        name="results.csv",
        force=force,
        version=version,
        sep=",",
        chunksize=CHUNKSIZE,
        usecols=[0, 1, 2, 3, 5],
    )
    return df


class AntibodyRegistryGetter(Obo):
    """An ontology representation of the Antibody Registry."""

    ontology = bioversions_key = PREFIX
    typedefs = [has_citation]

    def iter_terms(self, force: bool = False) -> Iterable[Term]:
        """Iterate over terms in the ontology."""
        return iter_terms(force=force, version=self._version_or_raise)


# TODO there are tonnnnsss of mappings to be curated
MAPPING: Mapping[str, str | None] = {
    "AMERICAN DIAGNOSTICA": None,  # No website
    "Biolegend": "biolegend",
    "Enzo Life Sciences": "enzo",
    "Novus": "novus",
    "LifeSpan": "biozil",
    "Creative Diagnostics": None,  # This site doesn't have a provider for IDs
}

SKIP = {
    "Universi",
    "School",
    "201",
    "200",
    "199",
}


def iter_terms(*, force: bool = False, version: str | None = None) -> Iterable[Term]:
    """Iterate over antibodies."""
    chunks = get_chunks(force=force, version=version)
    needs_curating = set()
    # df['vendor'] = df['vendor'].map(bioregistry.normalize_prefix)
    it = tqdm(chunks, desc=f"{PREFIX}, chunkssize={CHUNKSIZE}")
    for chunk in it:
        for identifier, name, vendor, catalog_number, defining_citation in chunk.values:
            if pd.isna(identifier):
                continue
            identifier = removeprefix(identifier, "AB_")
            term = Term.from_triple(PREFIX, identifier, name if pd.notna(name) else None)
            if vendor not in MAPPING:
                if vendor not in needs_curating:
                    needs_curating.add(vendor)
                    if all(x not in vendor for x in SKIP):
                        logger.debug(f"! vendor {vendor} for {identifier}")
            elif MAPPING[vendor] is not None and pd.notna(catalog_number) and catalog_number:
                term.append_xref((MAPPING[vendor], catalog_number))  # type:ignore
            if defining_citation and pd.notna(defining_citation):
                for pubmed_id in defining_citation.split(","):
                    pubmed_id = pubmed_id.strip()
                    if not pubmed_id:
                        continue
                    term.append_provenance(Reference(prefix="pubmed", identifier=pubmed_id))
            yield term


if __name__ == "__main__":
    AntibodyRegistryGetter.cli()
