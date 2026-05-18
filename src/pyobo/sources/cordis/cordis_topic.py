"""Converter for CORDIS topics."""

from collections.abc import Iterable

from pyobo.sources.cordis.utils import TOPIC_PREFIX, clean_topic_id, open_cordis
from pyobo.struct import Obo, Term

__all__ = [
    "CordisTopicGetter",
]


class CordisTopicGetter(Obo):
    """An ontology representation of CORDIS topics."""

    ontology = TOPIC_PREFIX
    dynamic_version = True

    def iter_terms(self, force: bool = False) -> Iterable[Term]:
        """Iterate over terms in the ontology."""
        return iter_terms()


def iter_terms(version: str | None = None) -> Iterable[Term]:
    """Iterate over CORDIS topic terms."""
    with open_cordis("topics.csv", version=version) as reader:
        unique = {row["topic"]: row["title"] for row in reader}
        for identifier, name in sorted(unique.items()):
            yield Term.from_triple(TOPIC_PREFIX, clean_topic_id(identifier), name)


if __name__ == "__main__":
    CordisTopicGetter.cli(["--obo"])
