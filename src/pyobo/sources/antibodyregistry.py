# -*- coding: utf-8 -*-

"""Converter for the Antibody Registry."""

from typing import Iterable, Optional

import click
import pandas as pd
from more_click import verbose_option
from tqdm import tqdm

import bioregistry
import bioversions
from pyobo import Obo, Term
from pyobo.utils.path import ensure_df

PREFIX = "antibodyregistry"
URL = "http://antibodyregistry.org/php/fileHandler.php"
CHUNKSIZE = 20_000


def get_chunks(force: bool = False) -> pd.DataFrame:
    """Get the BioGRID identifiers mapping dataframe."""
    version = bioversions.get_version(PREFIX)
    df = ensure_df(
        PREFIX,
        url=URL,
        force=force,
        version=version,
        sep=",",
        chunksize=CHUNKSIZE,
        usecols=[0, 1, 2, 3, 5],
    )
    return df


def get_obo(*, force: bool = False) -> Obo:
    """Get the Antibody Registry as OBO."""
    return Obo(
        ontology=PREFIX,
        name=bioregistry.get_name(PREFIX),
        iter_terms=iter_terms,
        iter_terms_kwargs=dict(force=force),
        data_version=bioversions.get_version(PREFIX),
        auto_generated_by=f"bio2obo:{PREFIX}",
    )


MAPPING = {
    "AMERICAN DIAGNOSTICA": None,
    "Biolegend": "biolegend.antibody",
    "Enzo Life Sciences": "enzo.antibody",
}

SKIP = {
    "Universi",
    "School",
    "201",
    "200",
    "199",
}


def iter_terms(force: bool = False) -> Iterable[Term]:
    """Iterate over antibodies."""
    chunks = get_chunks(force=force)
    needs_curating = set()
    # df['vendor'] = df['vendor'].map(bioregistry.normalize_prefix)
    it = tqdm(chunks, desc=f"{PREFIX}, chunkssize={CHUNKSIZE}")
    for chunk in it:
        for identifier, name, vendor, catalog_number, defining_citation in chunk.values:
            term = Term.from_triple(PREFIX, identifier, name)
            if vendor not in MAPPING:
                if vendor not in needs_curating:
                    needs_curating.add(vendor)
                    if all(x not in vendor for x in SKIP):
                        it.write(f"! vendor {vendor} for {identifier}")
            elif MAPPING[vendor] is not None and pd.notna(catalog_number) and catalog_number:
                term.append_xref((MAPPING[vendor], catalog_number))
            if pd.notna(defining_citation):
                for pubmed_id in defining_citation.split(","):
                    pubmed_id = pubmed_id.strip()
                    if not pubmed_id:
                        continue
                    term.append_provenance(("pubmed", pubmed_id))
            yield term


@click.command()
@verbose_option
def _main():
    obo = get_obo(force=True)
    obo.write_default(force=True, write_obo=True)


if __name__ == "__main__":
    _main()
