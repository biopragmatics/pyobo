"""Converter for CORDIS organizations."""

from collections.abc import Iterable

from curies import vocabulary as v

from pyobo import Obo, Reference, Term
from pyobo.sources.cordis.utils import ORGANIZATION_PREFIX, open_cordis
from pyobo.struct.typedef import has_homepage

__all__ = [
    "CordisOrganizationGetter",
]

ABBREVIATION = Reference.from_reference(v.abbreviation)


class CordisOrganizationGetter(Obo):
    """An ontology representation of CORDIS organizations."""

    ontology = ORGANIZATION_PREFIX
    typedefs = [has_homepage]
    dynamic_version = True

    def iter_terms(self, force: bool = False) -> Iterable[Term]:
        """Iterate over terms in the ontology."""
        return iter_terms()


def iter_terms(version: str | None = None) -> Iterable[Term]:
    """Iterate over CORDIS organization terms."""
    with open_cordis("organization.csv", version=version) as reader:
        seen = set()
        for row in reader:
            identifier = row["organisationID"]
            if identifier in seen:
                continue
            seen.add(identifier)
            term = Term(
                reference=Reference(
                    prefix=ORGANIZATION_PREFIX, identifier=identifier, name=row["name"]
                )
            )
            if short_name := row["shortName"]:
                term.append_synonym(short_name, type=ABBREVIATION)
            if url := row["organizationURL"]:
                term.annotate_uri(has_homepage, url)
            if vat := row["vatNumber"]:
                term.append_exact_match(Reference(prefix="vat", identifier=vat))
            term.append_exact_match(Reference(prefix="eu.rcn", identifier=row["rcn"]))
            # TODO city, country, nutsCode
            yield term


if __name__ == "__main__":
    CordisOrganizationGetter.cli(["--obo"])
