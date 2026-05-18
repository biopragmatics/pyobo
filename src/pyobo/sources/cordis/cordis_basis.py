"""Converter for CORDIS legal bases."""

from collections.abc import Iterable

from pyobo.sources.cordis.utils import open_cordis
from pyobo.struct import Obo, Term

__all__ = [
    "CordisBasisGetter",
]

PREFIX = "cordis.basis"


class CordisBasisGetter(Obo):
    """An ontology representation of CORDIS legal bases."""

    ontology = PREFIX
    dynamic_version = True

    def iter_terms(self, force: bool = False) -> Iterable[Term]:
        """Iterate over terms in the ontology."""
        return iter_terms()


def iter_terms(version: str | None = None) -> Iterable[Term]:
    """Iterate over CORDIS legal basis terms."""
    with open_cordis("project.csv", version=version) as reader:
        unique = {row["legalBasis"]: row["title"] for row in reader}
        for identifier, name in sorted(unique):
            yield Term.from_triple(PREFIX, identifier, name)

    # TODO implement some kind of hierarchy?


if __name__ == "__main__":
    CordisBasisGetter.cli()
