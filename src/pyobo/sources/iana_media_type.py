"""An ontology representation of IANA media types (i.e. MIME types).

.. seealso:: https://www.iana.org/assignments/media-types/media-types.xhtml
"""

from collections.abc import Iterable

import requests

from pyobo import Obo, Reference, Term, TypeDef, default_reference
from pyobo.struct import Annotation
from pyobo.struct.typedef import has_source, term_replaced_by
from pyobo.utils.path import ensure_df

__all__ = ["IANAGetter"]

PREFIX = "iana.mediatype"
ROOT_MEDIA_TYPE = Term.from_triple(prefix="dcterms", identifier="MediaType", name="media type")
ROOT_FILE_FORMAT = Term.from_triple(prefix="dcterms", identifier="FileFormat", name="file format")

#: The top-level types listed on https://www.iana.org/assignments/media-types/media-types.xhtml
MEDIA_TYPE_GROUPS = [
    "application",
    "audio",
    "font",
    "haptics",
    "image",
    "message",
    "model",
    "multipart",
    "text",
    "video",
]

GROUP_TO_CSV = {
    media_type_group: (
        f"https://www.iana.org/assignments/media-types/{media_type_group}.csv",
        Term(
            reference=Reference(prefix=PREFIX, identifier=media_type_group, name=media_type_group)
        ).append_parent(ROOT_MEDIA_TYPE),
    )
    for media_type_group in MEDIA_TYPE_GROUPS
}

MIMETYPE_IO_URL = (
    "https://github.com/patrickmccallum/mimetype-io/raw/refs/heads/master/src/mimeData.json"
)


def _get_mimetypes():
    records = requests.get(MIMETYPE_IO_URL, timeout=5).json()
    rv = {}
    for record in records:
        name = record.pop("name")
        rv[name] = record
    return rv


PREDICATE = TypeDef(
    reference=default_reference(
        prefix=PREFIX, identifier="extension", name="appears with file extension"
    ),
    domain=ROOT_MEDIA_TYPE.reference,
    range=ROOT_FILE_FORMAT.reference,
    definition="Connects a media type with a file format that has been observed to encode it",
    is_metadata_tag=True,
)


class IANAGetter(Obo):
    """An ontology representation of IANA media types (i.e. MIME types)."""

    ontology = bioregistry_key = PREFIX
    name = "IANA Media Types"
    dynamic_version = True
    root_terms = [ROOT_MEDIA_TYPE.reference, ROOT_FILE_FORMAT.reference]
    typedefs = [
        term_replaced_by,
        PREDICATE,
    ]

    def iter_terms(self, force: bool = False) -> Iterable[Term]:
        """Iterate over terms in the ontology."""
        return get_terms()


def get_terms() -> Iterable[Term]:
    """Get IANA Media Type terms."""
    mimetypes_data = _get_mimetypes()

    filetype_to_term = {}
    for record in mimetypes_data.values():
        for filetype_str in record.get("fileTypes", []):
            filetype_id = filetype_str.removeprefix(".")
            filetype_term = Term(
                reference=default_reference(PREFIX, identifier=filetype_id, name=filetype_str),
                type="Instance",
            )
            filetype_term.append_parent(ROOT_FILE_FORMAT)
            filetype_term.annotate_string(has_source, MIMETYPE_IO_URL)
            filetype_to_term[filetype_str] = filetype_term
            yield filetype_term

    terms: dict[str, Term] = {}
    forwards: dict[Term, str] = {}
    for key, (url, parent) in GROUP_TO_CSV.items():
        df = ensure_df(PREFIX, url=url, sep=",")
        terms[key] = parent
        for name, identifier, references in df.values:
            mimetypes_record = mimetypes_data.get(identifier, {})

            if "OBSOLE" in name or "DEPRECATED" in name:
                is_obsolete = True
            else:
                is_obsolete = None

            term = Term(
                reference=Reference(prefix=PREFIX, identifier=identifier, name=name),
                is_obsolete=is_obsolete,
                # TODO how to add definition source?
                definition=mimetypes_record.get("description"),
            ).append_parent(parent)
            for reference in _process_references(references):
                term.append_see_also_uri(reference)
            terms[identifier.casefold()] = term

            for filetype_str in mimetypes_record.get("fileTypes", []):
                term.annotate_object(
                    PREDICATE,
                    filetype_to_term[filetype_str],
                    annotations=[Annotation.uri(has_source, MIMETYPE_IO_URL)],
                )

            if "in favor of" in name:
                _, _, new = name.partition("in favor of ")
                forwards[term] = new.casefold().strip().rstrip(")").strip()

    for old, new in forwards.items():
        if new == "vnd.afpc.afplinedata":
            new = "application/vnd.afpc.afplinedata"
        old.append_replaced_by(terms[new].reference)

    yield from terms.values()


def _process_references(cell: str) -> list[str]:
    rv = []
    for part in cell.split("]["):
        part = part.strip("[").strip("]")
        if part.startswith("RFC"):
            rv.append(f"https://www.iana.org/go/rfc{part.removeprefix('RFC')}")
    return rv


if __name__ == "__main__":
    IANAGetter.cli()
