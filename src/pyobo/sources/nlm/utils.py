"""Utilities for NLM."""

from collections.abc import Iterable
from xml.etree import ElementTree

from tqdm import tqdm

from pyobo import Reference, Term, TypeDef, default_reference, ensure_path
from pyobo.struct.struct import CHARLIE_TERM, PYOBO_INJECTED
from pyobo.struct.typedef import has_end_date, has_start_date
from pyobo.utils.path import ensure_df

PREFIX_CATALOG = "nlm"
PREFIX_PUBLISHER = "nlm.publisher"

CATALOG_TO_PUBLISHER = "https://ftp.ncbi.nlm.nih.gov/pubmed/xmlprovidernames.txt"
JOURNAL_INFO_PATH = "https://ftp.ncbi.nlm.nih.gov/pubmed/jourcache.xml"
PUBLISHED_IN = TypeDef(
    reference=default_reference(PREFIX_CATALOG, "published_in", name="published in"),
    xrefs=[
        Reference(prefix="biolink", identifier="published_in"),
        Reference(prefix="uniprot.core", identifier="publishedIn"),
    ],
)
JOURNAL_TERM = (
    Term(reference=default_reference(PREFIX_CATALOG, "journal", name="journal"))
    .append_exact_match(Reference(prefix="SIO", identifier="000160"))
    .append_exact_match(Reference(prefix="FBCV", identifier="0000787"))
    .append_exact_match(Reference(prefix="MI", identifier="0885"))
    .append_exact_match(Reference(prefix="bibo", identifier="Journal"))
    .append_exact_match(Reference(prefix="uniprot.core", identifier="Journal"))
    .append_contributor(CHARLIE_TERM)
    .append_comment(PYOBO_INJECTED)
)
PUBLISHER_TERM = (
    Term(reference=default_reference(PREFIX_CATALOG, "publisher", name="publisher"))
    .append_exact_match(Reference(prefix="biolink", identifier="publisher"))
    .append_exact_match(Reference(prefix="schema", identifier="publisher"))
    .append_exact_match(Reference(prefix="uniprot.core", identifier="publisher"))
    .append_contributor(CHARLIE_TERM)
    .append_comment(PYOBO_INJECTED)
)


def get_publishers(*, force: bool = False) -> dict[str, Term]:
    """Get NLM publishers."""
    journal_to_publisher_df = ensure_df(
        PREFIX_CATALOG, url=CATALOG_TO_PUBLISHER, sep="|", force=force, dtype=str
    )
    journal_id_to_publisher_key: dict[str, Term] = {
        journal_id: Term(
            reference=Reference(prefix=PREFIX_PUBLISHER, identifier=identifier, name=name),
            type="Instance",
        ).append_parent(PUBLISHER_TERM)
        for journal_id, identifier, name in journal_to_publisher_df.values
    }
    return journal_id_to_publisher_key


def get_journals(
    *, force: bool = False, journal_id_to_publisher_key: dict[str, Term] | None = None
) -> Iterable[Term]:
    """Get NLM Catalog terms."""
    path = ensure_path(PREFIX_CATALOG, url=JOURNAL_INFO_PATH, force=force)
    root = ElementTree.parse(path).getroot()

    if journal_id_to_publisher_key is None:
        journal_id_to_publisher_key = get_publishers(force=force)
    elements = root.findall("Journal")
    for element in elements:
        if term := _process_journal(element, journal_id_to_publisher_key):
            yield term


def _process_journal(element, journal_id_to_publisher_key: dict[str, Term]) -> Term | None:
    # TODO enrich with context from https://ftp.ncbi.nlm.nih.gov/pubmed/J_Entrez.txt and https://ftp.ncbi.nlm.nih.gov/pubmed/J_Medline.txt

    nlm_id = element.findtext("NlmUniqueID")
    name = element.findtext("Name")

    if not nlm_id.isnumeric():
        # TODO investigate these records, which all appear to have IDs that
        #  end in R like 17410670R (Proceedings of the staff meetings. Honolulu. Clinic)
        #  which corresponds to https://www.ncbi.nlm.nih.gov/nlmcatalog/287649
        return None

    issns = [(issn.text, issn.attrib["type"]) for issn in element.findall("Issn")]
    # ActivityFlag is either "0" or "1"
    term = Term(
        reference=Reference(prefix=PREFIX_CATALOG, identifier=nlm_id, name=name),
        type="Instance",
    )
    term.append_parent(JOURNAL_TERM)
    for synonym in element.findall("Alias"):
        term.append_synonym(synonym.text)
    for issn, _issn_type in issns:
        if issn.isnumeric():
            issn = issn[:4] + "-" + issn[4:]

        # TODO include ISSN type, this is important
        #  to determine a "canonical" one
        term.append_xref(Reference(prefix="issn", identifier=issn))
    if start_year := element.findtext("StartYear"):
        if len(start_year) != 4:
            tqdm.write(f"[{term.curie}] invalid start year: {start_year}")
        else:
            term.annotate_year(has_start_date, start_year)
    if end_year := element.findtext("EndYear"):
        if len(end_year) != 4:
            tqdm.write(f"[{term.curie}] invalid end year: {end_year}")
        else:
            term.annotate_year(has_end_date, end_year)
    # FIXME this whole thing needs reinvestigating
    if publisher_reference := journal_id_to_publisher_key.get(term.identifier):
        term.annotate_object(PUBLISHED_IN, publisher_reference.reference)
    return term
