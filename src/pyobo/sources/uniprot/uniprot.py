# -*- coding: utf-8 -*-

"""Converter for UniProt."""

from pathlib import Path
from typing import Iterable, Optional

import bioversions
from tqdm import tqdm

from pyobo import Obo
from pyobo.constants import RAW_MODULE
from pyobo.struct import Term, from_species
from pyobo.utils.io import open_reader

PREFIX = "uniprot"
REVIEWED_URL = (
    "https://www.uniprot.org/uniprot/"
    "?query=reviewed:yes&format=tab&force=true&columns=id,entry%20name,organism-id,context&sort=id&compress=yes"
)


def get_obo(force: bool = False) -> Obo:
    """Get UniProt as OBO."""
    # Just throw out force
    version = bioversions.get_version("uniprot")
    return Obo(
        ontology=PREFIX,
        name="UniProt",
        data_version=version,
        iter_terms=iter_terms,
        iter_terms_kwargs=dict(version=version),
        typedefs=[from_species],
        auto_generated_by=f"bio2obo:{PREFIX}",
    )


def iter_terms(version: Optional[str] = None, force: bool = False) -> Iterable[Term]:
    """Iterate over UniProt Terms."""
    with open_reader(ensure(version=version, force=force)) as reader:
        _ = next(reader)  # header
        for uniprot_id, name, taxonomy_id in tqdm(reader, desc="Mapping UniProt"):
            term = Term.from_triple(prefix=PREFIX, identifier=uniprot_id, name=name)
            # TODO add gene encodes from relationship
            # TODO add description
            term.set_species(taxonomy_id)
            yield term


def ensure(version: Optional[str] = None, force: bool = False) -> Path:
    """Ensure the reviewed uniprot names are available."""
    if version is None:
        version = bioversions.get_version("uniprot")
    return RAW_MODULE.ensure(PREFIX, version, name="reviewed.tsv.gz", url=REVIEWED_URL, force=force)


if __name__ == "__main__":
    get_obo().write_default(force=True, write_obo=True, write_obograph=True)
