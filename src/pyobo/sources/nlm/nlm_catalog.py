"""Converter for NLM Providers.

To ground NLM catalog entries, after installing PyOBO with
``pip install pyobo[sources]``, do the following:

.. code-block:: python

    import pyobo

    grounder = pyobo.get_grounder("nlm")
    match = grounder.get_best_match("Angewandte Chemie International Edition")
    print(match.identifier, match.score)
"""

from collections.abc import Iterable

from pyobo.sources.nlm.utils import (
    ISSN_TYPE,
    JOURNAL_TERM,
    PREFIX_CATALOG,
    PUBLISHER_TERM,
    get_catalog_terms,
)
from pyobo.struct import CHARLIE_TERM, HUMAN_TERM, Obo, Term
from pyobo.struct.typedef import (
    exact_match,
    has_comment,
    has_creator,
    has_end_date,
    has_language,
    has_publisher,
    has_start_date,
    has_subject,
)

__all__ = [
    "NLMCatalogGetter",
]


class NLMCatalogGetter(Obo):
    """An ontology representation of NLM Providers."""

    bioversions_key = ontology = PREFIX_CATALOG
    dynamic_version = True
    typedefs = [
        ISSN_TYPE,
        has_end_date,
        has_start_date,
        has_subject,
        exact_match,
        has_comment,
        has_creator,
        has_publisher,
        has_language,
    ]
    root_terms = [JOURNAL_TERM.reference, PUBLISHER_TERM.reference]

    def iter_terms(self, force: bool = False) -> Iterable[Term]:
        """Iterate over journal terms for NLM Catalog."""
        yield JOURNAL_TERM
        yield CHARLIE_TERM
        yield HUMAN_TERM
        yield from get_catalog_terms(force=force)


if __name__ == "__main__":
    NLMCatalogGetter.cli()
