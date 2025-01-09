"""Converter for NLM Providers."""

from collections.abc import Iterable
from xml.etree import ElementTree

from pyobo.struct import Obo, Reference, Term, TypeDef, default_reference
from pyobo.struct.typedef import exact_match, has_end_date, has_start_date
from pyobo.utils.path import ensure_df, ensure_path

__all__ = [
    "NLMCatalogGetter",
]

PREFIX = "nlm"
CATALOG_TO_PUBLISHER = "https://ftp.ncbi.nlm.nih.gov/pubmed/xmlprovidernames.txt"
JOURNAL_INFO_PATH = "https://ftp.ncbi.nlm.nih.gov/pubmed/jourcache.xml"

# see also , https://w3id.org/biolink/vocab/published_in
PUBLISHED_IN = TypeDef(
    reference=default_reference(PREFIX, "published_in", name="published in"),
    xrefs=[
        Reference(prefix="biolink", identifier="published_in"),
        Reference(prefix="uniprot.core", identifier="publishedIn"),
    ],
)

JOURNAL_TERM = (
    Term(reference=default_reference(PREFIX, "journal", name="journal"))
    .append_exact_match(Reference(prefix="SIO", identifier="000160"))
    .append_exact_match(Reference(prefix="FBCV", identifier="0000787"))
    .append_exact_match(Reference(prefix="MI", identifier="0885"))
    .append_exact_match(Reference(prefix="bibo", identifier="Journal"))
    .append_exact_match(Reference(prefix="uniprot.core", identifier="Journal"))
)
PUBLISHER_TERM = (
    Term(reference=default_reference(PREFIX, "publisher", name="publisher"))
    .append_exact_match(Reference(prefix="biolink", identifier="publisher"))
    .append_exact_match(Reference(prefix="schema", identifier="publisher"))
    .append_exact_match(Reference(prefix="uniprot.core", identifier="publisher"))
)


# TODO enrich with context from https://ftp.ncbi.nlm.nih.gov/pubmed/J_Entrez.txt and https://ftp.ncbi.nlm.nih.gov/pubmed/J_Medline.txt


class NLMCatalogGetter(Obo):
    """An ontology representation of NLM Providers."""

    bioversions_key = ontology = PREFIX
    dynamic_version = True
    typedefs = [PUBLISHED_IN, has_end_date, has_start_date, exact_match]
    root_terms = [JOURNAL_TERM.reference, PUBLISHER_TERM.reference]
    idspaces = {
        PREFIX: "https://www.ncbi.nlm.nih.gov/nlmcatalog/",
        "nlm.publisher": "https://bioregistry.io/nlm.publisher:",
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
    }

    def iter_terms(self, force: bool = False) -> Iterable[Term]:
        """Iterate over gene terms for NLM Catalog."""
        yield from get_terms(force=force)


def get_terms(force: bool = False) -> Iterable[Term]:
    """Get NLM Catalog terms."""
    yield JOURNAL_TERM
    yield PUBLISHER_TERM

    path = ensure_path(PREFIX, url=JOURNAL_INFO_PATH)
    root = ElementTree.parse(path).getroot()

    journal_to_publisher_df = ensure_df(
        PREFIX, url=CATALOG_TO_PUBLISHER, sep="|", force=force, dtype=str
    )
    journal_id_to_publisher_key: dict[str, Reference] = {
        journal_id: Reference(prefix="nlm.publisher", identifier=identifier, name=name)
        for journal_id, identifier, name in journal_to_publisher_df.values
    }
    elements = root.findall("Journal")
    for element in elements:
        yield _process_journal(element, journal_id_to_publisher_key)
    for k in sorted(set(journal_id_to_publisher_key.values())):
        yield Term(reference=k, type="Instance").append_parent(PUBLISHER_TERM)


def _process_journal(element, journal_id_to_publisher_key: dict[str, Reference]) -> Term:
    nlm_id = element.findtext("NlmUniqueID")
    name = element.findtext("Name")
    issns = [(issn.text, issn.attrib["type"]) for issn in element.findall("Issn")]
    # ActivityFlag is either "0" or "1"
    term = Term(
        reference=Reference(prefix=PREFIX, identifier=nlm_id, name=name),
        type="Instance",
    )
    term.append_parent(JOURNAL_TERM)
    for synonym in element.findall("Alias"):
        term.append_synonym(synonym.text)
    for issn, _issn_type in issns:
        # TODO include ISSN type, this is important
        #  to determine a "canonical" one
        term.append_xref(Reference(prefix="issn", identifier=issn))
    if start_year := element.findtext("StartYear"):
        term.annotate_year(has_start_date, start_year)
    if end_year := element.findtext("EndYear"):
        term.annotate_year(has_end_date, end_year)
    # FIXME this whole thing needs reinvestigating
    if publisher_reference := journal_id_to_publisher_key.get(term.identifier):
        term.annotate_object(PUBLISHED_IN, publisher_reference)
    return term


if __name__ == "__main__":
    NLMCatalogGetter.cli()
