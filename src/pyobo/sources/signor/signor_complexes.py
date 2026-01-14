"""A source for SIGNOR complexes."""

from collections.abc import Iterable

import pandas as pd

from pyobo import Obo, Reference, Term, default_reference
from pyobo.sources.signor.download import DownloadKey, get_signor_df
from pyobo.struct import CHARLIE_TERM, HUMAN_TERM, PYOBO_INJECTED
from pyobo.struct.typedef import exact_match, has_component, has_member

__all__ = [
    "SignorGetter",
]

PREFIX = "signor"

PROTEIN_FAMILY = (
    Term(reference=default_reference(PREFIX, "protein-family"))
    .append_contributor(CHARLIE_TERM)
    .append_comment(PYOBO_INJECTED)
)
PROTEIN_COMPLEX = (
    Term(reference=default_reference(PREFIX, "protein-complex"))
    .append_contributor(CHARLIE_TERM)
    .append_comment(PYOBO_INJECTED)
)
PHENOTYPE = (
    Term(reference=default_reference(PREFIX, "phenotype"))
    .append_contributor(CHARLIE_TERM)
    .append_comment(PYOBO_INJECTED)
)
STIMULUS = (
    Term(reference=default_reference(PREFIX, "stimulus"))
    .append_contributor(CHARLIE_TERM)
    .append_comment(PYOBO_INJECTED)
)
ROOT_TERMS = (PROTEIN_FAMILY, PROTEIN_COMPLEX, PHENOTYPE, STIMULUS)


class SignorGetter(Obo):
    """An ontology representation of SIGNOR complexes."""

    ontology = bioversions_key = PREFIX
    typedefs = [exact_match, has_component, has_member]
    root_terms = [r.reference for r in ROOT_TERMS]

    def iter_terms(self, force: bool = False) -> Iterable[Term]:
        """Iterate over terms in the ontology."""
        return iter_terms(version=self._version_or_raise, force=force)


def iter_terms(version: str, force: bool = False) -> Iterable[Term]:
    """Iterate over terms."""
    yield CHARLIE_TERM
    yield HUMAN_TERM
    yield from ROOT_TERMS

    complexes_df = get_signor_df(PREFIX, version=version, force=force, key=DownloadKey.complex)
    for identifier, name, proteins in complexes_df.values:
        term = Term.from_triple(PREFIX, identifier, name)
        term.append_parent(PROTEIN_COMPLEX)
        for part_id in proteins.split(","):
            part_id = part_id.strip()
            if part_id.startswith("SIGNOR-"):
                part = Reference(prefix="signor", identifier=part_id)
            elif part_id.startswith("CHEBI:"):
                part = Reference(prefix="chebi", identifier=part_id.removeprefix("CHEBI:"))
            else:
                part = Reference(prefix="uniprot", identifier=part_id)
            term.annotate_object(has_component, part)
        yield term

    family_df = get_signor_df(PREFIX, version=version, force=force, key=DownloadKey.family)
    for identifier, name, proteins in family_df.values:
        term = Term.from_triple(PREFIX, identifier, name)
        term.append_parent(PROTEIN_FAMILY)
        for uniprot_id in proteins.split(","):
            uniprot_id = uniprot_id.strip()
            term.annotate_object(has_member, Reference(prefix="uniprot", identifier=uniprot_id))
        yield term

    stimulus_df = get_signor_df(PREFIX, version=version, force=force, key=DownloadKey.stimulus)
    # for some reason, there are many duplicates in this file
    stimulus_df = stimulus_df.drop_duplicates()
    for identifier, name, description in stimulus_df.values:
        term = Term.from_triple(PREFIX, identifier, name, definition=_clean_descr(description))
        term.append_parent(STIMULUS)
        yield term

    phenotypes_df = get_signor_df(PREFIX, version=version, force=force, key=DownloadKey.phenotype)
    for identifier, name, description in phenotypes_df.values:
        term = Term.from_triple(PREFIX, identifier, name, definition=_clean_descr(description))
        term.append_parent(PHENOTYPE)
        yield term


def _clean_descr(d) -> str | None:
    if pd.isna(d):
        return None
    return d.replace("\n", " ")


if __name__ == "__main__":
    SignorGetter.cli()
