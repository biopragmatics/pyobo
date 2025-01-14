"""A source for ClinicalTrials.gov."""

from collections.abc import Iterable

from clinicaltrials_downloader import get_studies

from pyobo import Obo, Reference, Term, default_reference
from pyobo.struct.struct import CHARLIE_TERM, HUMAN_TERM, PYOBO_INJECTED
from pyobo.struct.typedef import has_category, has_contributor

__all__ = [
    "ClinicalTrialsGetter",
]

PREFIX = "clinicaltrials"
DEFAULT_FIELDS = [
    "NCTId",
    "BriefTitle",
    "Condition",
    "ConditionMeshTerm",  # ConditionMeshTerm is the name of the disease
    "ConditionMeshId",
    "InterventionName",  # InterventionName is the name of the drug/vaccine
    "InterventionType",
    "InterventionMeshTerm",
    "InterventionMeshId",
    "StudyType",
    "DesignAllocation",
    "OverallStatus",
    "Phase",
    "WhyStopped",
    "SecondaryIdType",
    "SecondaryId",
    "StartDate",  # Month [day], year: "November 1, 2023", "May 1984" or NaN
    "StartDateType",  # "Actual" or "Anticipated" (or NaN)
    "ReferencePMID",  # these are tagged as relevant by the author, but not necessarily about the trial
]

CLINICAL_TRIAL_TERM = (
    Term(reference=default_reference(PREFIX, "clinical-trial", name="clinical trial"))
    .annotate_object(has_contributor, CHARLIE_TERM)
    .append_comment(PYOBO_INJECTED)
    .append_see_also_uri("https://github.com/obi-ontology/obi/issues/1831#issuecomment-2587810590")
)


class ClinicalTrialsGetter(Obo):
    """Get the ClinicalTrials.gov database as an ontology."""

    ontology = PREFIX
    dynamic_version = True
    typedefs = [has_contributor, has_category]

    def iter_terms(self, force: bool = False) -> Iterable[Term]:
        """Iterate over terms for studies."""
        yield CLINICAL_TRIAL_TERM
        yield CHARLIE_TERM
        yield HUMAN_TERM
        yield from iterate_studies()


def iterate_studies(*, force: bool = False) -> Iterable[Term]:
    """Iterate over terms for studies."""
    for study in get_studies(force=force):
        yield _process_study(study)


def _process_study(raw_study) -> Term:
    protocol_section = raw_study["protocolSection"]
    identification_module = protocol_section["identificationModule"]
    identifier = identification_module["nctId"]
    name = identification_module["officialTitle"]
    synonym = identification_module["briefTitle"]
    design_module = protocol_section["design_module"]
    study_type = design_module["studyType"]
    term = Term(reference=Reference(prefix=PREFIX, identifier=identifier, name=name))
    term.append_synonym(synonym)
    # TODO make the study type into inheritance
    term.annotate_literal(has_category, study_type)
    term.append_parent(CLINICAL_TRIAL_TERM)
    return term
