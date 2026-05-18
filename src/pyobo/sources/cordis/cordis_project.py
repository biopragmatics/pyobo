"""Converter for CORDIS projects."""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable

from curies import vocabulary as v
from tabulate import tabulate
from tqdm import tqdm

from pyobo import Obo, Reference, Term, TypeDef, default_reference
from pyobo.sources.cordis.utils import (
    BASIS_PREFIX,
    ORGANIZATION_PREFIX,
    PROJECT_PREFIX,
    TOPIC_PREFIX,
    clean_topic_id,
    open_cordis,
)
from pyobo.struct.typedef import has_participant

__all__ = [
    "CordisProjectGetter",
]

# see euscivoc, which is in skosxl format

PROJECT = Term.from_triple("foaf", "Project", "project")
STATUS = Term(reference=default_reference(PROJECT_PREFIX, "status"))
KEY_TO_STATUS = {
    "CLOSED": Term(reference=default_reference(PROJECT_PREFIX, "closed")).append_parent(STATUS),
    "SIGNED": Term(reference=default_reference(PROJECT_PREFIX, "signed")).append_parent(STATUS),
    "TERMINATED": Term(reference=default_reference(PROJECT_PREFIX, "terminated")).append_parent(
        STATUS
    ),
}

HAS_LEGAL_BASIS = TypeDef(
    reference=default_reference(PROJECT_PREFIX, "hasLegalBasis"), domain=PROJECT.reference
)
HAS_TOPIC = TypeDef(
    reference=default_reference(PROJECT_PREFIX, "hasTopic"), domain=PROJECT.reference
)
HAS_FUNDING_SCHEME = TypeDef(
    reference=default_reference(PROJECT_PREFIX, "hasFundingScheme"),
    domain=PROJECT.reference,
    range=Reference.from_reference(v.xsd_string),
)
HAS_KEYWORD = TypeDef(  # TODO replace with SDO
    reference=default_reference(PROJECT_PREFIX, "hasKeyword"),
    range=Reference.from_reference(v.xsd_string),
    domain=PROJECT.reference,
)
HAS_STATUS = TypeDef(
    reference=default_reference(PROJECT_PREFIX, "hasStatus"), domain=PROJECT.reference
)
HAS_START = TypeDef(
    reference=default_reference(PROJECT_PREFIX, "hasStart"),
    domain=PROJECT.reference,
    range=Reference.from_reference(v.xsd_date),
)
HAS_END = TypeDef(
    reference=default_reference(PROJECT_PREFIX, "hasEnd"),
    domain=PROJECT.reference,
    range=Reference.from_reference(v.xsd_date),
)
ACRONYM = Reference.from_reference(v.acronym)


class CordisProjectGetter(Obo):
    """An ontology representation of cordis projects."""

    ontology = PROJECT_PREFIX
    typedefs = [
        HAS_LEGAL_BASIS,
        HAS_TOPIC,
        HAS_FUNDING_SCHEME,
        HAS_KEYWORD,
        HAS_STATUS,
        HAS_START,
        HAS_END,
    ]
    dynamic_version = True
    root_terms = [STATUS.reference, PROJECT.reference]

    def iter_terms(self, force: bool = False) -> Iterable[Term]:
        """Iterate over terms in the ontology."""
        return iter_terms()


def iter_terms(*, version: str | None = None) -> Iterable[Term]:
    """Iterate over CORDIS project terms."""
    terms: dict[str, Term] = {}
    scheme_counter: Counter[str] = Counter()
    with open_cordis("project.csv", version=version) as reader:
        for row in reader:
            term = Term(
                reference=Reference(
                    prefix="cordis.project", identifier=row["id"], name=row["title"]
                ),
                # definition=row['objective'],
            ).append_parent(PROJECT)
            term.append_synonym(row["acronym"], type=ACRONYM)
            term.annotate_object(
                HAS_LEGAL_BASIS, Reference(prefix=BASIS_PREFIX, identifier=row["legalBasis"])
            )

            doi = row["grantDoi"]
            try:
                doi_reference = Reference(prefix="doi", identifier=doi)
            except ValueError:
                tqdm.write(f"[{term.curie}] problem with DOI: {doi}")
                continue
            else:
                term.append_exact_match(doi_reference)

            try:
                rcn_id = Reference(prefix="eu.rcn", identifier=row["rcn"])
            except ValueError:
                pass  # this is probably the same offset issue as above
                # tqdm.write(f"[{term.curie}] problem with RCN: {doi}")
            else:
                term.append_exact_match(rcn_id)

            for topic in row["topics"].split(","):
                term.annotate_object(
                    HAS_TOPIC, Reference(prefix=TOPIC_PREFIX, identifier=clean_topic_id(topic))
                )

            for keyword in row["keywords"].split(","):
                if keyword_stripped := keyword.strip().strip('"').strip():
                    term.annotate_string(HAS_KEYWORD, keyword_stripped)

            if funding_scheme := row["fundingScheme"]:
                scheme_counter[row["fundingScheme"]] += 1
                term.annotate_string(HAS_FUNDING_SCHEME, funding_scheme)

            if start_date := row["startDate"]:
                term.annotate_date(HAS_START, start_date)
            if end_date := row["endDate"]:
                term.annotate_date(HAS_END, end_date)

            term.annotate_object(HAS_STATUS, KEY_TO_STATUS[row["status"]])

            terms[term.identifier] = term

    tqdm.write(tabulate(scheme_counter.most_common()))

    with open_cordis("organization.csv", version=version) as reader:
        for row in reader:
            project_id = row["projectID"]
            organization_id = row["organisationID"]
            if project_id not in terms:
                continue
            terms[project_id].annotate_object(
                has_participant,
                Reference(prefix=ORGANIZATION_PREFIX, identifier=organization_id),
                # TODO can add all sorts of annotations from this file, like the cost, role, ordinal
            )

    yield PROJECT
    yield STATUS
    yield from KEY_TO_STATUS.values()
    yield from terms.values()


if __name__ == "__main__":
    CordisProjectGetter.cli(["--obo"])
