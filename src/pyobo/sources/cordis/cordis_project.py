"""Converter for CORDIS projects."""

from collections.abc import Iterable

from curies import vocabulary as v
from tqdm import tqdm

from pyobo import Obo, Reference, Term, TypeDef, default_reference
from pyobo.sources.cordis.utils import (
    BASIS_PREFIX,
    ORGANIZATION_PREFIX,
    PROJECT_PREFIX,
    open_cordis,
)
from pyobo.struct.typedef import has_participant

__all__ = [
    "CordisProjectGetter",
]

# see euscivoc, which is in skosxl format

HAS_LEGAL_BASIS = TypeDef(reference=default_reference(PROJECT_PREFIX, "hasLegalBasis"))
ACRONYM = Reference.from_reference(v.acronym)


class CordisProjectGetter(Obo):
    """An ontology representation of cordis projects."""

    ontology = PROJECT_PREFIX
    typedefs = [HAS_LEGAL_BASIS]
    dynamic_version = True

    def iter_terms(self, force: bool = False) -> Iterable[Term]:
        """Iterate over terms in the ontology."""
        return iter_terms()


def iter_terms(*, version: str | None = None) -> Iterable[Term]:
    """Iterate over CORDIS project terms."""
    terms: dict[str, Term] = {}
    with open_cordis("project.csv", version=version) as reader:
        for row in reader:
            term = Term(
                reference=Reference(
                    prefix="cordis.project", identifier=row["id"], name=row["title"]
                ),
                # definition=row['objective'],
            )
            term.append_synonym(row["acronym"], type=ACRONYM)
            term.annotate_object(
                HAS_LEGAL_BASIS, Reference(prefix=BASIS_PREFIX, identifier=row["legalBasis"])
            )

            doi = row["grantDoi"]
            try:
                doi_reference = Reference(prefix="doi", identifier=doi)
            except ValueError:
                tqdm.write(f"[{term.curie}] problem with DOI: {doi}")
            else:
                term.append_exact_match(doi_reference)
            terms[term.identifier] = term

    with open_cordis("organization.csv", version=version) as reader:
        for row in reader:
            project_id = row["projectID"]
            organization_id = row["organisationID"]
            terms[project_id].annotate_object(
                has_participant,
                Reference(prefix=ORGANIZATION_PREFIX, identifier=organization_id),
                # TODO can add all sorts of annotations from this file, like the cost, role, ordinal
            )

    yield from terms.values()


if __name__ == "__main__":
    CordisProjectGetter.cli()
