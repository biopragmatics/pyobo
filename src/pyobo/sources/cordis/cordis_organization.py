"""Converter for CORDIS organizations."""

from collections.abc import Iterable

from pyobo import Obo, Reference, Term
from pyobo.sources.cordis.utils import open_cordis

__all__ = [
    "CordisOrganizationGetter",
]

PREFIX = "cordis.organization"


class CordisOrganizationGetter(Obo):
    """An ontology representation of CORDIS organizations."""

    ontology = PREFIX
    dynamic_version = True

    def iter_terms(self, force: bool = False) -> Iterable[Term]:
        """Iterate over terms in the ontology."""
        return iter_terms()


def iter_terms(version: str | None = None) -> Iterable[Term]:
    """Iterate over CPT terms."""
    # TODO might need to add additional parts
    with open_cordis("organization.csv", version=version) as reader:
        for row in reader:
            term = Term(
                reference=Reference(
                    prefix="cordis.project", identifier=row["id"], name=row["title"]
                ),
            )
            yield term


if __name__ == "__main__":
    CordisOrganizationGetter.cli(["--obo"])
