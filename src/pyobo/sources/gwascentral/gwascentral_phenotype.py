"""Converter for GWAS Central Phenotypes."""

import json
from collections.abc import Iterable

from tqdm.auto import tqdm, trange

from pyobo.struct import Obo, Reference, Term
from pyobo.utils.path import ensure_path

from .gwascentral_study import VERSION

__all__ = [
    "GWASCentralPhenotypeGetter",
]

PREFIX = "gwascentral.phenotype"


class GWASCentralPhenotypeGetter(Obo):
    """An ontology representation of GWAS Central's phenotype nomenclature."""

    ontology = PREFIX
    static_version = VERSION

    def iter_terms(self, force: bool = False) -> Iterable[Term]:
        """Iterate over terms in the ontology."""
        return iter_terms(force=force, version=self._version_or_raise)


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
                backend="requests",
                timeout=1,
            )
        except OSError as e:
            tqdm.write(f"{n}: {e}")
            continue
        with path.open() as file:
            j = json.load(file)

        description = j.get("description")
        if description is not None:
            description = description.strip().replace("\n", " ")
        term = Term(
            reference=Reference(prefix=PREFIX, identifier=j["identifier"], name=j["name"]),
            definition=description,
        )
        yield term


if __name__ == "__main__":
    GWASCentralPhenotypeGetter.cli()
