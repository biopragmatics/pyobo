# -*- coding: utf-8 -*-

"""Converter for GWAS Central Phenotypes."""

import json
from typing import Iterable

from tqdm import tqdm, trange

from pyobo.sources.gwascentral_study import VERSION
from pyobo.struct import Obo, Reference, Term
from pyobo.utils.path import ensure_path

PREFIX = "gwascentral.phenotype"


def get_obo() -> Obo:
    """Get GWAS Central Studies as OBO."""
    return Obo(
        name="GWAS Central Phenotype",
        ontology=PREFIX,
        iter_terms=iter_terms,
        iter_terms_kwargs=dict(version=VERSION),
        data_version=VERSION,
        auto_generated_by=f"bio2obo:{PREFIX}",
    )


def iter_terms(version: str) -> Iterable[Term]:
    """Iterate over terms from GWAS Central Phenotype."""
    for n in trange(1, 11000, desc=f"{PREFIX} download"):
        try:
            path = ensure_path(
                PREFIX,
                "phenotype",
                version=version,
                url=f"https://www.gwascentral.org/phenotype/HGVPM{n}?format=json",
                name=f"HGVPM{n}.json",
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
    get_obo().write_default()
