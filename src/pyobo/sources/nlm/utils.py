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


"""
-------------  ------
D020492        207102 Periodical
D020500         18127
D016435         11697
D016423          9406
D020504          8028
D020501          6076
D016417          5239
D019494          2938
D020481          2551
D020470          1971
D016454          1605
D019487          1430
D020485          1378
D020479           984
D020496           605
D002363           515
D020475           420
D020488           201
D019215           190
D019542           159
D019482           153
D000078922        152
D020484           120
D020502           118
D002382           115
D016431           111
D017065           108
D020507            86
D019991            80
D016437            71
D020466            67
D020490            65
D000078903         63
D019539            62
D016418            61
D022921            60
D020474            35
D002378            34
D020503            34
D020489            33
D019525            33
D000078925         31
D000078929         30
D016427            28
D020467            28
D020478            27
D020463            26
D020495            26
D020468            23
D019500            23
D023362            21
D020498            20
D020497            17
D019532            15
D020469            14
D000077202         13
D020465            13
D000078984         12
D000077823         12
D020505            12
D017418             9
D016453             9
D018486             8
D019531             8
D055824             7
D019493             7
D062210             7
D019509             7
D057405             6
D029282             6
D020476             6
D019497             6
D017203             6
D016447             5
D019480             5
D055821             5
D018848             4
D020471             4
D000078182          4
D020480             4
D022922             4
D064886             3
D000078928          3
D019492             3
(DNLM)D020492       3
D020482             2
D019484             2

"""

# TODO when do we classify as a journal?
#  use record.publication_type_mesh_ids
SX: dict[str, Reference] = {}


def catalog_record_to_term(record: CatalogRecord) -> Term | None:
    """Construct a PyOBO term from a :class:`pubmed_downloader.Journal`."""
    term = Term(
        reference=Reference(
            prefix=PREFIX_CATALOG, identifier=record.nlm_catalog_id, name=record.title
        ),
        type="Instance",
    )
    for mesh_id in record.publication_type_mesh_ids:
        if parent := SX.get(mesh_id):
            term.append_parent(parent)
        else:
            term.append_parent(Reference(prefix="mesh", identifier=mesh_id))
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
