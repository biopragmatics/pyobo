# -*- coding: utf-8 -*-

"""Converter for GWAS Central Phenotypes."""

import json
from typing import Iterable

from tqdm import tqdm, trange

from pyobo.sources.gwascentral_study import VERSION
from pyobo.struct import Obo, Reference, Term
from pyobo.utils.path import ensure_path

__all__ = [
    "GWASCentralPhenotypeGetter",
]

PREFIX = "gwascentral.phenotype"


class GWASCentralPhenotypeGetter(Obo):
    ontology = PREFIX
    data_version = VERSION

    def iter_terms(self, force: bool = False) -> Iterable[Term]:
        """Iterate over terms in the ontology."""
        return iter_terms(force=force, version=self.data_version)


def get_obo(force: bool = False) -> Obo:
    """Get GWAS Central Studies as OBO."""
    return GWASCentralPhenotypeGetter(force=force)


def iter_terms(version: str, force: bool = False) -> Iterable[Term]:
    """Iterate over terms from GWAS Central Phenotype."""
    for n in trange(1, 11000, desc=f"{PREFIX} download"):
        try:
            path = ensure_path(
                PREFIX,
                "phenotype",
                version=version,
                url=f"https://www.gwascentral.org/phenotype/HGVPM{n}?format=json",
                name=f"HGVPM{n}.json",
                force=force,
            )
        except OSError as e:
            tqdm.write(f"{n}: {e}")
            continue
        with open(path) as file:
            j = json.load(file)
        term = Term(
            reference=Reference(PREFIX, j["identifier"], j["name"]),
            definition=j["description"].strip().replace("\n", " "),
        )
        yield term


if __name__ == "__main__":
    get_obo().cli()
