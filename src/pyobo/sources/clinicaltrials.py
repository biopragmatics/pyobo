"""A source for ClinicalTrials.gov."""

from collections.abc import Iterable

from clinicaltrials_downloader import get_studies_slim

from pyobo import Obo, Reference, Term, default_reference
from pyobo.struct.struct import CHARLIE_TERM, HUMAN_TERM, PYOBO_INJECTED
from pyobo.struct.typedef import has_contributor

__all__ = [
    "ClinicalTrialsGetter",
]

PREFIX = "clinicaltrials"

STUDY = Term(reference=default_reference(PREFIX, "study", name="study"))

CLINICAL_TRIAL_TERM = Term(
    reference=default_reference(PREFIX, "clinical-trial", name="clinical trial")
).append_parent(STUDY)

INTERVENTIONAL = Term(
    reference=default_reference(
        PREFIX, "interventional-clinical-trial", name="interventional clinical trial"
    )
).append_parent(CLINICAL_TRIAL_TERM)

OBSERVATIONAL = Term(
    reference=default_reference(
        PREFIX, "observational-clinical-trial", name="observational clinical trial"
    )
).append_parent(CLINICAL_TRIAL_TERM)

EXPANDED_ACCESS = Term(
    reference=default_reference(
        PREFIX, "expanded-access-study", name="expanded access study"
    )
).append_parent(STUDY)

TERMS = [STUDY, CLINICAL_TRIAL_TERM, OBSERVATIONAL, INTERVENTIONAL, EXPANDED_ACCESS]
PARENTS: dict[str | None, Term] = {
    "INTERVENTIONAL": INTERVENTIONAL,
    "OBSERVATIONAL": OBSERVATIONAL,
    "EXPANDED_ACCESS": EXPANDED_ACCESS,
    None: STUDY,
}


class ClinicalTrialsGetter(Obo):
    """Get the ClinicalTrials.gov database as an ontology."""

    ontology = PREFIX
    dynamic_version = True
    typedefs = [has_contributor]
    root_terms = [STUDY]

    def iter_terms(self, force: bool = False) -> Iterable[Term]:
        """Iterate over terms for studies."""
        yield CHARLIE_TERM
        yield HUMAN_TERM
        for term in TERMS:
            term.annotate_object(has_contributor, CHARLIE_TERM)
            term.append_comment(PYOBO_INJECTED)
            yield term
        yield from iterate_studies()


def iterate_studies(*, force: bool = False) -> Iterable[Term]:
    """Iterate over terms for studies."""
    studies = get_studies_slim(force=force)
    for study in studies:
        yield _process_study(study)


def _process_study(raw_study) -> Term:
    protocol_section = raw_study["protocolSection"]
    identification_module = protocol_section["identificationModule"]
    identifier = identification_module["nctId"]

    name = identification_module.get("officialTitle")
    synonym = identification_module.get("briefTitle")
    if synonym and not name:
        name, synonym = synonym, None

    term = Term(
        reference=Reference(prefix=PREFIX, identifier=identifier, name=name), type="Instance"
    )
    if synonym:
        term.append_synonym(synonym)

    design_module = protocol_section.get("designModule", {})
    study_type = design_module.get("studyType")
    term.append_parent(PARENTS[study_type])
    return term


if __name__ == "__main__":
    ClinicalTrialsGetter.cli()
