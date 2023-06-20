# -*- coding: utf-8 -*-

"""Converter for UniProt."""

from pathlib import Path
from typing import Iterable, Optional

import bioversions
from tqdm.auto import tqdm

from pyobo import Obo, Reference
from pyobo.constants import RAW_MODULE
from pyobo.identifier_utils import standardize_ec
from pyobo.struct import Term, enables, from_species
from pyobo.utils.io import open_reader

PREFIX = "uniprot"
REVIEWED_URL = (
    "https://rest.uniprot.org/uniprotkb/stream?compressed=true"
    "&fields=accession%2Cid%2Corganism_id%2Cprotein_name%2Cec%2Clit_pubmed_id%2Cxref_pdb"
    "&format=tsv&query=%28%2A%29%20AND%20%28reviewed%3Atrue%29"
)


class UniProtGetter(Obo):
    """An ontology representation of the UniProt database."""

    bioversions_key = ontology = PREFIX
    typedefs = [from_species, enables]

    def iter_terms(self, force: bool = False) -> Iterable[Term]:
        """Iterate over terms in the ontology."""
        yield from iter_terms(force=force, version=self._version_or_raise)


def get_obo(force: bool = False) -> Obo:
    """Get UniProt as OBO."""
    return UniProtGetter(force=force)


def iter_terms(version: Optional[str] = None, force: bool = False) -> Iterable[Term]:
    """Iterate over UniProt Terms."""
    with open_reader(ensure(version=version, force=force)) as reader:
        _ = next(reader)  # header
        for uniprot_id, name, taxonomy_id, _synonyms, ecs, pubmeds, pdbs in tqdm(
            reader, desc="Mapping UniProt", unit_scale=True
        ):
            term = Term.from_triple(prefix=PREFIX, identifier=uniprot_id, name=name)
            # TODO add gene encodes from relationship
            # TODO add description
            term.set_species(taxonomy_id)
            if ecs:
                for ec in ecs.split(";"):
                    term.append_relationship(
                        enables, Reference(prefix="eccode", identifier=standardize_ec(ec))
                    )
            for pubmed in pubmeds.split(";"):
                if pubmed:
                    term.append_provenance(Reference(prefix="pubmed", identifier=pubmed.strip()))
            for pdb in pdbs.split(";"):
                if pdb:
                    term.append_xref(Reference(prefix="pdb", identifier=pdb.strip()))
            yield term


def ensure(version: Optional[str] = None, force: bool = False) -> Path:
    """Ensure the reviewed uniprot names are available."""
    if version is None:
        version = bioversions.get_version("uniprot")
    return RAW_MODULE.ensure(PREFIX, version, name="reviewed.tsv.gz", url=REVIEWED_URL, force=force)


if __name__ == "__main__":
    UniProtGetter.cli()
