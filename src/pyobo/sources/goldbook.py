"""An ontology representation of IUPAC Gold Book."""

import json.decoder
import re
from collections.abc import Iterable

import pystow.utils
import requests
from curies.vocabulary import abbreviation
from tqdm import tqdm

from pyobo.struct import Obo, Reference, Term, TypeDef, default_reference
from pyobo.struct import vocabulary as v
from pyobo.struct.typedef import is_mentioned_by
from pyobo.utils.path import ensure_path

PREFIX = "goldbook"
URL = "https://goldbook.iupac.org/terms/index/all/json/download"
TERM_URL_FORMAT = "https://goldbook.iupac.org/terms/view/{}/json"

HAS_STATUS = TypeDef(reference=default_reference(PREFIX, "hasStatus"), is_metadata_tag=True)


class GoldBookGetter(Obo):
    """An ontology representation of IUPAC Gold Book."""

    ontology = PREFIX
    dynamic_version = True
    typedefs = [HAS_STATUS, is_mentioned_by]

    def iter_terms(self, force: bool = False) -> Iterable[Term]:
        """Iterate over terms in the ontology."""
        return _iter_terms()


def _iter_terms() -> Iterable[Term]:
    res = requests.get(URL, timeout=15).json()
    seen_document_references = set()
    yield Term(reference=v.document)
    for identifier in tqdm(res["terms"]["list"], unit_scale=True):
        term, document_references = _get_term(identifier)
        if term and document_references:
            yield term
            for document_reference in document_references:
                if document_reference not in seen_document_references:
                    seen_document_references.add(document_reference)
                    yield Term(reference=document_reference, type="Instance").append_parent(
                        v.document
                    )


def _get_term(
    identifier: str, *, verbose: bool = False
) -> tuple[None, None] | tuple[Term, list[Reference]]:
    url = TERM_URL_FORMAT.format(identifier)
    try:
        path = ensure_path(PREFIX, "terms", url=url, name=f"{identifier}.json")
    except pystow.utils.DownloadError:
        if verbose:
            tqdm.write(f"[{PREFIX}:{identifier}] failed to download {url}")
        return None, None

    try:
        with path.open() as file:
            res = json.load(file)
    except json.decoder.JSONDecodeError:
        if verbose:
            tqdm.write(f"[{PREFIX}:{identifier}] failed to parse data in {path}")
        return None, None

    record = res["term"]
    definition_blocks = record.pop("definitions")
    if definition_blocks:
        definition_block = definition_blocks[0]
        definition = _clean(definition_block["text"])
    else:
        definition_block = None
        definition = None

    documents = []

    term = Term(
        reference=Reference(
            prefix=PREFIX,
            identifier=identifier,
            name=record.pop("title").strip(),
        ),
        definition=definition,
    )
    if definition_block:
        for note in definition_block.get("notes", {}).values():
            term.append_comment(note)
        for link in definition_block.get("links", {}):
            link_id = link["url"].removeprefix("https://goldbook.iupac.org//terms/view/")
            try:
                link_reference = Reference(prefix=PREFIX, identifier=link_id)
            except ValueError:
                if link["term"] is not None:
                    tqdm.write(f"[{PREFIX}:{identifier}] failed to parse link URL: {link['url']}")
            else:
                term.append_see_also(link_reference)
        for source in definition_block.get("sources", []):
            if source_doi := _extract_doi(source):
                source_reference = Reference(prefix="doi", identifier=source_doi)
                documents.append(source_reference)
                term.append_mentioned_by(source_reference)

    if status := record.pop("status", None):
        term.annotate_string(HAS_STATUS, status)

    if initialism := record.pop("initialism", None):
        if initialism.startswith("<em>initialism</em>:"):
            initialism = initialism.removeprefix("<em>initialism</em>:").strip()
            term.append_synonym(initialism, type=Reference.from_reference(abbreviation))

    if synonym := record.pop("synonym", None):
        if synonym.startswith("<"):
            if synonym.startswith("<em>synonym</em>:"):
                synonym = synonym.removeprefix("<em>synonym</em>:")
                term.append_synonym(_clean(synonym))
            elif synonym.startswith("<em>synonyms</em>:"):
                for s in synonym.removeprefix("<em>synonyms</em>:").strip().split(","):
                    term.append_synonym(_clean(s))
            else:
                tqdm.write(f"[{term.curie}] issue with synonym: {synonym}")

    for x in SKIP_KEYS:
        if x in record:
            del record[x]

    if record:
        tqdm.write(f"[{identifier}] unhandled keys: {record.keys()}")

    return term, documents


SKIP_KEYS = [
    "id",
    "longtitle",
    "code",
    "altoutputs",
    "citation",
    "license",
    "collection",
    "disclaimer",
    "accessed",
    "doi",
    "mentioned",  # TODO see goldbook:15155
    "also defines",  # TODO see goldbook:A00003
    "index",  # TODO see goldbook:A00543
    "abbrev",  # TODO see goldbook:AT06994
    "acronym",  # TODO see goldbook:09400
    "antonym",  # TODO see goldbook:13110
    "related",  # TODO see goldbook:C01245
    "intro",  # TODO see goldbook:Q04991
]

DOI_RE = re.compile(r"10\.\d{4,}/\S+")


def _extract_doi(text: str) -> str | None:
    match = DOI_RE.search(text)
    if not match:
        return None
    doi = match.group(0)
    # Strip common trailing punctuation
    return doi.rstrip(".,;:)'\"")


def _clean(s: str) -> str:
    return (
        s.strip()
        .replace("\\n", " ")
        .replace("\n", " ")
        .replace("\r", " ")
        .strip()
        .strip('"')
        .strip()
    )


if __name__ == "__main__":
    GoldBookGetter.cli()
