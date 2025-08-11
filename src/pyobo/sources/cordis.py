"""Converter for CORDIS Projects."""

from collections.abc import Iterable

from pyobo import Obo, Reference, Term
from pyobo.utils.path import ensure_path
from pystow.utils import read_zipfile_csv

__all__ = [
    "CordisProjectGetter",
]

URL = "https://cordis.europa.eu/data/cordis-h2020projects-csv.zip"
PREFIX = "cordis.project"

# see euscivoc, which is in skosxl format


class CordisProjectGetter(Obo):
    """An ontology representation of cordis projects."""

    ontology = PREFIX
    dynamic_version = True

    def iter_terms(self, force: bool = False) -> Iterable[Term]:
        """Iterate over terms in the ontology."""
        return iter_terms()


def iter_terms() -> Iterable[Term]:
    """Iterate over CPT terms."""
    path = ensure_path("cordis", url=URL)
    df = read_zipfile_csv(path, "project.csv", sep='\t')
    print(df.head())


if __name__ == "__main__":
    CordisProjectGetter.cli()
