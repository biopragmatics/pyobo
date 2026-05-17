"""Converter for CORDIS Projects."""

from collections.abc import Iterable

from pystow.utils import open_zip_reader

from pyobo import Obo, Term
from pyobo.sources.cordis.utils import get_cordis_path

__all__ = [
    "CordisBasisGetter",
]

PREFIX = "cordis.basis"


class CordisBasisGetter(Obo):
    """An ontology representation of cordis legal bases."""

    ontology = PREFIX
    dynamic_version = True

    def iter_terms(self, force: bool = False) -> Iterable[Term]:
        """Iterate over terms in the ontology."""
        return iter_terms()


def iter_terms() -> Iterable[Term]:
    """Iterate over CORDIS legal basis terms."""
    path = get_cordis_path()
    with open_zip_reader(path, "legalBasis.csv", delimiter=";") as reader:
        _header = next(reader)
        unique = {row[1] for row in reader}
        for identifier in sorted(unique):
            yield Term.from_triple(PREFIX, identifier)


if __name__ == "__main__":
    CordisBasisGetter.cli(["--obo"])
