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
    studies = get_studies(force=force)
    for study in studies:
        yield _process_study(study)



ENCOUNTERED_STUDY_TYPES = set()


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

    # TODO make the study type into inheritance, when available
    design_module = protocol_section.get("design_module", {})
    study_type = design_module.get("studyType")
    if study_type:
        term.annotate_literal(has_category, study_type)
        ENCOUNTERED_STUDY_TYPES.add(study_type)
    term.append_parent(CLINICAL_TRIAL_TERM)

    return term


if __name__ == "__main__":
    ClinicalTrialsGetter.cli()
