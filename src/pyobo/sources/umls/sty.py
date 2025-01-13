"""Converter for UMLS Semantic Types."""

from collections.abc import Iterable

from pyobo import Obo, Reference, Term, default_reference
from pyobo.struct.typedef import has_category
from pyobo.utils.path import ensure_df

__all__ = [
    "UMLSSTyGetter",
]

PREFIX = "sty"

URL = "https://www.nlm.nih.gov/research/umls/knowledge_sources/semantic_network/SemGroups.txt"


class UMLSSTyGetter(Obo):
    """An ontology representation of UMLS Semantic Types."""

    ontology = PREFIX
    bioversions_key = "umls"
    typedefs = [has_category]

    def iter_terms(self, force: bool = False) -> Iterable[Term]:
        """Iterate over terms in the ontology."""
        return iter_terms(version=self._version_or_raise)


COLUMNS = [
    "group",
    "group_label",
    "sty_id",
    "sty_name",
]


def iter_terms(version: str) -> Iterable[Term]:
    """Iterate over UMLS terms."""
    df = ensure_df(PREFIX, url=URL, version=version, sep="|", header=None, names=COLUMNS)

    extras = {
        group: Term(
            reference=default_reference(PREFIX, group, name=group_label),
        )
        for group, group_label in df[["group", "group_label"]].drop_duplicates().values
    }
    yield from extras.values()

    for group, _group_label, sty_id, sty_name in df.values:
        term = Term(reference=Reference(prefix="sty", identifier=sty_id, name=sty_name))
        term.append_parent(extras[group])
        yield term


if __name__ == "__main__":
    UMLSSTyGetter.cli()
