"""A source for ClinicalTrials.gov."""

from collections.abc import Iterable

from clinicaltrials_downloader import get_studies_slim

from pyobo import Obo, Reference, Term, TypeDef, default_reference
from pyobo.struct.struct import CHARLIE_TERM, HUMAN_TERM, PYOBO_INJECTED
from pyobo.struct.typedef import has_contributor

__all__ = [
    "ClinicalTrialsGetter",
]

PREFIX = "clinicaltrials"

INVESTIGATES_CONDITION = TypeDef(
    reference=default_reference(
        prefix=PREFIX, identifier="investigates_condition", name="investigates condition"
    ),
    is_metadata_tag=True,
)
HAS_INTERVENTION = TypeDef(
    reference=default_reference(
        prefix=PREFIX, identifier="has_intervention", name="has intervention"
    ),
    is_metadata_tag=True,
)

STUDY_TERM = Term(reference=default_reference(PREFIX, "study", name="study"))

CLINICAL_TRIAL_TERM = Term(
    reference=default_reference(PREFIX, "clinical-trial", name="clinical trial")
).append_parent(STUDY_TERM)

INTERVENTIONAL_CLINICAL_TRIAL_TERM = Term(
    reference=default_reference(
        PREFIX, "interventional-clinical-trial", name="interventional clinical trial"
    )
).append_parent(CLINICAL_TRIAL_TERM)

RANDOMIZED_INTERVENTIONAL_CLINICAL_TRIAL_TERM = Term(
    reference=default_reference(
        PREFIX,
        "randomized-interventional-clinical-trial",
        name="randomized interventional clinical trial",
    )
).append_parent(INTERVENTIONAL_CLINICAL_TRIAL_TERM)

NON_RANDOMIZED_INTERVENTIONAL_CLINICAL_TRIAL_TERM = Term(
    reference=default_reference(
        PREFIX,
        "non-randomized-interventional-clinical-trial",
        name="non-randomized interventional clinical trial",
    )
).append_parent(INTERVENTIONAL_CLINICAL_TRIAL_TERM)

OBSERVATIONAL_CLINICAL_TRIAL_TERM = Term(
    reference=default_reference(
        PREFIX, "observational-clinical-trial", name="observational clinical trial"
    )
).append_parent(CLINICAL_TRIAL_TERM)

EXPANDED_ACCESS_STUDY_TERM = Term(
    reference=default_reference(PREFIX, "expanded-access-study", name="expanded access study")
).append_parent(STUDY_TERM)

TERMS = [
    STUDY_TERM,
    CLINICAL_TRIAL_TERM,
    OBSERVATIONAL_CLINICAL_TRIAL_TERM,
    INTERVENTIONAL_CLINICAL_TRIAL_TERM,
    EXPANDED_ACCESS_STUDY_TERM,
    RANDOMIZED_INTERVENTIONAL_CLINICAL_TRIAL_TERM,
    NON_RANDOMIZED_INTERVENTIONAL_CLINICAL_TRIAL_TERM,
]

# These were identified as the 4 possibilities for study
# types in ClinicalTrials.gov. See summary script at
# https://gist.github.com/cthoyt/12a3cb3c63ad68d73fe5a2f0d506526f
PARENTS: dict[tuple[str | None, str | None], Term] = {
    ("INTERVENTIONAL", None): INTERVENTIONAL_CLINICAL_TRIAL_TERM,
    ("INTERVENTIONAL", "NA"): INTERVENTIONAL_CLINICAL_TRIAL_TERM,
    ("INTERVENTIONAL", "RANDOMIZED"): RANDOMIZED_INTERVENTIONAL_CLINICAL_TRIAL_TERM,
    ("INTERVENTIONAL", "NON_RANDOMIZED"): NON_RANDOMIZED_INTERVENTIONAL_CLINICAL_TRIAL_TERM,
    ("OBSERVATIONAL", None): OBSERVATIONAL_CLINICAL_TRIAL_TERM,
    ("EXPANDED_ACCESS", None): EXPANDED_ACCESS_STUDY_TERM,
    (None, None): STUDY_TERM,
}


class ClinicalTrialsGetter(Obo):
    """Get the ClinicalTrials.gov database as an ontology."""

    ontology = PREFIX
    dynamic_version = True
    typedefs = [has_contributor, INVESTIGATES_CONDITION, HAS_INTERVENTION]
    root_terms = [STUDY_TERM.reference]

    def iter_terms(self, force: bool = False) -> Iterable[Term]:
        """Iterate over terms for studies."""
        yield CHARLIE_TERM
        yield HUMAN_TERM
        for term in TERMS:
            term.append_contributor(CHARLIE_TERM)
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
    allocation = design_module.get("designInfo", {}).get("allocation")
    term.append_parent(PARENTS[study_type, allocation])

    references_module = protocol_section.get("referencesModule", {})
    for reference in references_module.get("references", []):
        if pubmed_id := reference.get("pmid"):
            term.append_see_also(Reference(prefix="pubmed", identifier=pubmed_id))

    derived_section = raw_study["derivedSection"]
    for mesh_record in derived_section.get("conditionBrowseModule", {}).get("meshes", []):
        term.annotate_object(INVESTIGATES_CONDITION, _mesh(mesh_record))

    for mesh_record in derived_section.get("interventionBrowseModule", {}).get("meshes", []):
        term.annotate_object(HAS_INTERVENTION, _mesh(mesh_record))
    return term


def _mesh(mesh_record: dict[str, str]) -> Reference:
    return Reference(
        prefix="mesh", identifier=mesh_record["id"], name=mesh_record.get("term") or None
    )


if __name__ == "__main__":
    ClinicalTrialsGetter.cli()
