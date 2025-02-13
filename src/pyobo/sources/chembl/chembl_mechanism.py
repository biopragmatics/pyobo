"""Converter for ChEMBL mechanisms."""

import logging
from collections.abc import Iterable

import chembl_downloader

from pyobo.struct import CHARLIE_TERM, PYOBO_INJECTED, Obo, Term
from pyobo.struct.typedef import exact_match

__all__ = [
    "ChEMBLMechanismGetter",
]

logger = logging.getLogger(__name__)

PREFIX = "chembl.mechanism"
QUERY = "SELECT * from ACTION_TYPE"

ROOT = (
    Term.default(PREFIX, "mechanism", name="mechanism")
    .append_contributor(CHARLIE_TERM)
    .append_comment(PYOBO_INJECTED)
)


class ChEMBLMechanismGetter(Obo):
    """An ontology representation of ChEMBL mechanisms."""

    ontology = PREFIX
    bioversions_key = "chembl"
    typedefs = [exact_match]
    root_terms = [ROOT.reference]

    def iter_terms(self, force: bool = False) -> Iterable[Term]:
        """Iterate over terms in the ontology."""
        return iter_terms(version=self._version_or_raise)


def normalize_chembl_mechanism(name: str) -> str:
    """Normalize a ChEMBL mechanism name into an identifier."""
    return name.lower().replace(" ", "-")


def _norm_name(name: str) -> str:
    return name.lower().replace("rnai ", "RNAi ")


def get_pattern(version: str | None = None) -> str:
    """Get a pattern."""
    df = chembl_downloader.query("SELECT action_type from ACTION_TYPE", version=version)
    parts = "|".join(sorted(normalize_chembl_mechanism(name) for (name,) in df.values))
    return f"^[{parts}]$"


def iter_terms(version: str) -> Iterable[Term]:
    """Iterate over ChEMBL mechanisms."""
    df = chembl_downloader.query(QUERY, version=version)
    terms = {}
    parents = {}
    for name, _description, parent in df.values:
        identifier = normalize_chembl_mechanism(name)
        terms[name] = Term.from_triple(prefix=PREFIX, identifier=identifier, name=_norm_name(name))
        if name != parent:  # protect against "other" which is a child of itself
            parents[name] = parent
    for child, parent in parents.items():
        terms[child].append_parent(terms[parent])

    # these are the three top-level things in the hierarchy, which
    # we annotate onto a dummy parent term
    for name in [
        "POSITIVE MODULATOR",
        "NEGATIVE MODULATOR",
        "OTHER",
    ]:
        terms[name].append_parent(ROOT)
    yield from terms.values()


if __name__ == "__main__":
    ChEMBLMechanismGetter.cli()
