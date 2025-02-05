"""Converter for NLM Providers."""

from collections.abc import Iterable

from pyobo.sources.nlm.utils import PREFIX_PUBLISHER, PUBLISHER_TERM, get_publishers
from pyobo.struct import CHARLIE_TERM, HUMAN_TERM, Obo, Term

__all__ = [
    "NLMPublisherGetter",
]


class NLMPublisherGetter(Obo):
    """An ontology representation of NLM Publishers."""

    bioversions_key = ontology = PREFIX_PUBLISHER
    dynamic_version = True
    root_terms = [PUBLISHER_TERM.reference]

    def iter_terms(self, force: bool = False) -> Iterable[Term]:
        """Iterate over gene terms for NLM Catalog."""
        yield from get_terms(force=force)


def get_terms(*, force: bool = False) -> Iterable[Term]:
    """Get NLM publisher terms."""
    yield PUBLISHER_TERM
    yield CHARLIE_TERM
    yield HUMAN_TERM

    journal_id_to_publisher_key = get_publishers(force=force)
    yield from sorted(set(journal_id_to_publisher_key.values()))


if __name__ == "__main__":
    NLMPublisherGetter.cli()
