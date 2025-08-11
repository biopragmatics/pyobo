"""An ontology representation of IANA media types (i.e. MIME types).

.. seealso:: https://www.iana.org/assignments/media-types/media-types.xhtml
"""

from collections.abc import Iterable

from pyobo import Obo, Reference, Term, default_reference
from pyobo.struct.typedef import term_replaced_by
from pyobo.utils.path import ensure_df

__all__ = ["IANAGetter"]

PREFIX = "iana.mediatype"
ROOT = Term.from_triple(prefix="dcterms", identifier="MediaType", name="media type")

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
        Term(reference=default_reference(PREFIX, media_type_group, media_type_group)).append_parent(
            ROOT
        ),
    )
    for media_type_group in MEDIA_TYPE_GROUPS
}


class IANAGetter(Obo):
    """An ontology representation of IANA media types (i.e. MIME types)."""

    ontology = bioregistry_key = PREFIX
    name = "IANA Media Types"
    dynamic_version = True
    root_terms = [t.reference for _, (_, t) in sorted(GROUP_TO_CSV.items())]
    typedefs = [
        term_replaced_by,
    ]

    def iter_terms(self, force: bool = False) -> Iterable[Term]:
        """Iterate over terms in the ontology."""
        return get_terms()


def get_terms() -> list[Term]:
    """Get IANA Media Type terms."""
    terms: dict[str, Term] = {}
    forwards: dict[Term, str] = {}
    for key, (url, parent) in GROUP_TO_CSV.items():
        df = ensure_df(PREFIX, url=url, sep=",")
        terms[key] = parent
        for name, identifier, references in df.values:
            if "OBSOLE" in name or "DEPRECATED" in name:
                is_obsolete = True
            else:
                is_obsolete = None
            term = Term(
                reference=Reference(prefix=PREFIX, identifier=identifier, name=name),
                is_obsolete=is_obsolete,
            ).append_parent(parent)
            for reference in _process_references(references):
                term.append_see_also_uri(reference)
            terms[identifier.casefold()] = term

            if "in favor of" in name:
                _, _, new = name.partition("in favor of ")
                forwards[term] = new.casefold().strip().rstrip(")").strip()

    for old, new in forwards.items():
        if new == "vnd.afpc.afplinedata":
            new = "application/vnd.afpc.afplinedata"
        old.append_replaced_by(terms[new].reference)

    return list(terms.values())


def _process_references(cell: str) -> list[str]:
    rv = []
    for part in cell.split("]["):
        part = part.strip("[").strip("]")
        if part.startswith("RFC"):
            rv.append(f"https://www.iana.org/go/rfc{part.removeprefix('RFC')}")
    return rv


if __name__ == "__main__":
    IANAGetter.cli()
