"""Converter for NLM Providers."""

from collections.abc import Iterable
from xml.etree import ElementTree

from pyobo.struct import Obo, Reference, Term, TypeDef, default_reference
from pyobo.utils.path import ensure_df, ensure_path

__all__ = [
    "NLMCatalogGetter",
]

PREFIX = "nlm"
CATALOG_TO_PUBLISHER = "https://ftp.ncbi.nlm.nih.gov/pubmed/xmlprovidernames.txt"
JOURNAL_INFO_PATH = "https://ftp.ncbi.nlm.nih.gov/pubmed/jourcache.xml"
PUBLISHER = TypeDef.default(PREFIX, "has_publisher", name="has publisher")
START_YEAR = TypeDef.default(PREFIX, "has_start_year", name="has start year")
END_YEAR = TypeDef.default(PREFIX, "has_end_year", name="has end year")


# TODO enrich with context from https://ftp.ncbi.nlm.nih.gov/pubmed/J_Entrez.txt and https://ftp.ncbi.nlm.nih.gov/pubmed/J_Medline.txt


class NLMCatalogGetter(Obo):
    """An ontology representation of NLM Providers."""

    bioversions_key = ontology = PREFIX
    dynamic_version = True
    typedefs = [PUBLISHER, START_YEAR, END_YEAR]
    idspaces = {
        PREFIX: "https://www.ncbi.nlm.nih.gov/nlmcatalog/",
    }

    def iter_terms(self, force: bool = False) -> Iterable[Term]:
        """Iterate over gene terms for NLM Catalog."""
        yield from get_terms()


def get_terms(force: bool = False) -> Iterable[Term]:
    """Get NLM Catalog terms."""
    path = ensure_path(PREFIX, url=JOURNAL_INFO_PATH)
    root = ElementTree.parse(path).getroot()

    journal_to_publisher_df = ensure_df(
        PREFIX, url=CATALOG_TO_PUBLISHER, sep="|", force=force, dtype=str
    )
    journal_id_to_publisher_key = {
        # TODO change to external prefix later
        journal_id: default_reference(PREFIX, key, name)
        for journal_id, key, name in journal_to_publisher_df.values
    }
    for element in root.findall("Journal"):
        term = _process_journal(element)
        if pr := journal_id_to_publisher_key.get(term.identifier):
            term.annotate_object(PUBLISHER, pr)
        yield term
    for k in sorted(set(journal_id_to_publisher_key.values())):
        yield Term(reference=k)


def _process_journal(element) -> Term:
    nlm_id = element.findtext("NlmUniqueID")
    name = element.findtext("Name")
    issns = [(issn.text, issn.attrib["type"]) for issn in element.findall("Issn")]
    # ActivityFlag is either "0" or "1"
    term = Term(
        reference=Reference(prefix=PREFIX, identifier=nlm_id, name=name),
    )
    for synonym in element.findall("Alias"):
        term.append_synonym(synonym.text)
    for issn, _issn_type in issns:
        term.append_xref(Reference(prefix="issn", identifier=issn))
    if start_year := element.findtext("StartYear"):
        term.annotate_integer(START_YEAR, start_year)
    if end_year := element.findtext("EndYear"):
        term.annotate_integer(END_YEAR, end_year)
    return term


if __name__ == "__main__":
    NLMCatalogGetter().cli()
