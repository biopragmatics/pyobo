"""Converter for NLM Providers."""

from collections.abc import Iterable

from pyobo.sources.nlm.utils import (
    JOURNAL_TERM,
    PREFIX_CATALOG,
    PREFIX_PUBLISHER,
    PUBLISHED_IN,
    PUBLISHER_TERM,
    get_journals,
    get_publishers,
)
from pyobo.struct import CHARLIE_TERM, HUMAN_TERM, Obo, Term
from pyobo.struct.typedef import exact_match, has_end_date, has_start_date

__all__ = [
    "NLMCatalogGetter",
]


class NLMCatalogGetter(Obo):
    """An ontology representation of NLM Providers."""

    bioversions_key = ontology = PREFIX_CATALOG
    dynamic_version = True
    typedefs = [PUBLISHED_IN, has_end_date, has_start_date, exact_match]
    root_terms = [JOURNAL_TERM.reference, PUBLISHER_TERM.reference]
    idspaces = {
        PREFIX_CATALOG: "https://www.ncbi.nlm.nih.gov/nlmcatalog/",
        PREFIX_PUBLISHER: "https://bioregistry.io/nlm.publisher:",
        "sio": "http://semanticscience.org/resource/SIO_",
        "schema": "http://schema.org/",
        "biolink": "https://w3id.org/biolink/vocab/",
        "MI": "http://purl.obolibrary.org/obo/MI_",
        "IAO": "http://purl.obolibrary.org/obo/IAO_",
        "bibo": "http://purl.org/ontology/bibo/",
        "FBcv": "http://purl.obolibrary.org/obo/FBcv_",
        "issn": "https://portal.issn.org/resource/ISSN/",
        "skos": "http://www.w3.org/2004/02/skos/core#",
        "uniprot.core": "http://purl.uniprot.org/core/",
        "dcat": "http://www.w3.org/ns/dcat#",
        "orcid": "https://orcid.org/",
        "NCBITaxon": "http://purl.obolibrary.org/obo/NCBITaxon_",
    }

    def iter_terms(self, force: bool = False) -> Iterable[Term]:
        """Iterate over journal terms for NLM Catalog."""
        yield from get_terms(force=force)


def get_terms(*, force: bool = False) -> Iterable[Term]:
    """Get NLM catalog terms."""
    yield JOURNAL_TERM
    yield PUBLISHER_TERM
    yield CHARLIE_TERM
    yield HUMAN_TERM

    journal_id_to_publisher_key = get_publishers(force=force)
    yield from sorted(set(journal_id_to_publisher_key.values()))

    yield from get_journals(force=force, journal_id_to_publisher_key=journal_id_to_publisher_key)


if __name__ == "__main__":
    NLMCatalogGetter.cli()
