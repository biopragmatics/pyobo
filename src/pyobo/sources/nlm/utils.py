"""Utilities for NLM."""

from __future__ import annotations

from collections.abc import Iterable

from pubmed_downloader.catalog import CatalogRecord, process_catalog

from pyobo import Annotation, Reference, Term, TypeDef, default_reference
from pyobo.struct.struct import CHARLIE_TERM, PYOBO_INJECTED, abbreviation
from pyobo.struct.typedef import (
    has_comment,
    has_creator,
    has_end_date,
    has_language,
    has_publisher,
    has_start_date,
    has_subject,
)
from pyobo.utils.path import ensure_df

PREFIX_CATALOG = "nlm"
PREFIX_PUBLISHER = "nlm.publisher"

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
ISSN_TYPE = TypeDef.default(
    PREFIX_CATALOG, "issn_type", name="ISSN type", predicate_type="annotation"
)


def get_publishers(*, force: bool = False) -> dict[str, Term]:
    """Get NLM publishers."""
    journal_to_publisher_df = ensure_df(
        PREFIX_CATALOG,
        url="https://ftp.ncbi.nlm.nih.gov/pubmed/xmlprovidernames.txt",
        sep="|",
        force=force,
        dtype=str,
    )
    journal_id_to_publisher_key: dict[str, Term] = {
        journal_id: Term(
            reference=Reference(prefix=PREFIX_PUBLISHER, identifier=identifier, name=name),
            type="Instance",
        ).append_parent(PUBLISHER_TERM)
        for journal_id, identifier, name in journal_to_publisher_df.values
    }
    return journal_id_to_publisher_key


def get_catalog_terms(*, force: bool = False, refresh_index: bool = True) -> Iterable[Term]:
    """Get NLM Catalog terms."""
    for catalog_record in process_catalog(force_process=force, refresh_index=refresh_index):
        if term := catalog_record_to_term(catalog_record):
            yield term


# TODO when do we classify as a journal?
#  use record.publication_type_mesh_ids
SX: dict[Reference, Reference] = {}


def catalog_record_to_term(record: CatalogRecord) -> Term | None:
    """Construct a PyOBO term from a :class:`pubmed_downloader.Journal`."""
    term = Term(
        reference=Reference(
            prefix=PREFIX_CATALOG, identifier=record.nlm_catalog_id, name=record.title
        ),
        type="Instance",
    )
    for publication_type in record.publication_types:
        if parent := SX.get(publication_type):  # type:ignore[call-overload]
            term.append_parent(parent)
        else:
            term.append_parent(publication_type)
    # TODO title sort?
    if record.medline_short_title:
        term.append_exact_synonym(record.medline_short_title, type=abbreviation)
    for title_alternative in record.title_alternatives:
        term.append_exact_synonym(
            title_alternative.text,
            annotations=[Annotation.string(has_comment, "title_alternative")],
        )
    for title_related in record.title_relatives:
        term.append_synonym(
            title_related.text, annotations=[Annotation.string(has_comment, "title_relatives")]
        )
    for xref in record.xrefs:
        try:
            term.append_xref(xref)
        except ValueError:
            # TODO add  DNLM:P05620000(s)
            #  failed to add xref: OCoLC:01793503
            continue
    for heading in record.headings:
        # TODO incorporate major/minor?
        term.append_relationship(has_subject, heading.reference)
    for issn in record.issns or []:
        try:
            issn_reference = Reference(prefix="issn", identifier=issn.value.replace(" ", ""))
        except ValueError:
            continue
            # tqdm.write(f"[{term.curie}] failed to add issn: {issn.value}")
        else:
            term.append_xref(
                issn_reference,
                annotations=[Annotation.string(predicate=ISSN_TYPE.reference, value=issn.type)],
            )
    if record.start_year is not None:
        term.annotate_year(has_start_date, record.start_year)
    if record.end_year is not None:
        term.annotate_year(has_end_date, record.end_year)
    for imprint in record.imprints:
        if imprint.reference:
            term.append_relationship(has_publisher, imprint.reference)
    for author in record.authors:
        if author_reference := author.get_reference():
            term.append_relationship(has_creator, author_reference)
    for collective in record.collectives:
        if collective.reference:
            term.append_relationship(has_creator, collective.reference)
    for language in record.languages:
        term.append_relationship(
            has_language,
            language.get_reference(),
            annotations=[Annotation.string(predicate=has_comment.reference, value=language.type)],
        )
    return term
