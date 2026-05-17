"""Converter for CORDIS Projects."""

from collections.abc import Iterable

from curies.vocabulary import acronym
from pystow.utils import open_zip_reader
from tqdm import tqdm

from pyobo import Obo, Reference, Term, TypeDef, default_reference
from pyobo.sources.cordis.utils import get_cordis_path

__all__ = [
    "CordisProjectGetter",
]

PREFIX = "cordis.project"


# see euscivoc, which is in skosxl format

HAS_LEGAL_BASIS = TypeDef(reference=default_reference(PREFIX, "hasLegalBasis"))


class CordisProjectGetter(Obo):
    """An ontology representation of cordis projects."""

    ontology = PREFIX
    typedefs = [HAS_LEGAL_BASIS]
    dynamic_version = True

    def iter_terms(self, force: bool = False) -> Iterable[Term]:
        """Iterate over terms in the ontology."""
        return iter_terms()


def iter_terms() -> Iterable[Term]:
    """Iterate over CPT terms."""
    path = get_cordis_path()
    # TODO might need to add additional parts
    with open_zip_reader(path, "project.csv", delimiter=";") as reader:
        header = next(reader)
        for row in reader:
            row = dict(zip(header, row, strict=False))
            term = Term(
                reference=Reference(
                    prefix="cordis.project", identifier=row["id"], name=row["title"]
                ),
                # definition=row['objective'],
            )
            term.append_synonym(row["acronym"], type=acronym)
            term.append_property(
                HAS_LEGAL_BASIS, Reference(prefix="cordis.basis", identifier=row["legalBasis"])
            )

            doi = row["grantDoi"]
            try:
                doi_reference = Reference(prefix="doi", identifier=doi)
            except ValueError:
                tqdm.write(f"[{term.curie}] problem with DOI: {doi}")
            else:
                term.append_exact_match(doi_reference)
            yield term


if __name__ == "__main__":
    CordisProjectGetter.cli(["--obo"])
