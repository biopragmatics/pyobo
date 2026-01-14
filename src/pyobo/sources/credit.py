"""Converter for the Contributor Roles Taxonomy."""

from __future__ import annotations

import json
from collections.abc import Iterable

from more_itertools import chunked

from pyobo.struct import CHARLIE_TERM, HUMAN_TERM, Obo, Reference, Term, default_reference
from pyobo.utils.path import ensure_path

__all__ = [
    "CreditGetter",
]

url = "https://api.github.com/repos/CASRAI-CRedIT/Dictionary/contents/Picklists/Contributor%20Roles"
PREFIX = "credit"
ROOT = default_reference(prefix=PREFIX, identifier="contributor-role", name="contributor role")
ROOT_TERM = (
    Term(reference=ROOT)
    .append_contributor(CHARLIE_TERM)
    .append_xref(Reference(prefix="cro", identifier="0000000"))
)


class CreditGetter(Obo):
    """An ontology representation of the Contributor Roles Taxonomy."""

    ontology = PREFIX
    static_version = "2022"
    root_terms = [ROOT]

    def iter_terms(self, force: bool = False) -> Iterable[Term]:
        """Iterate over terms in the ontology."""
        return get_terms(force=force)


def get_terms(force: bool = False) -> list[Term]:
    """Get terms from the Contributor Roles Taxonomy via GitHub."""
    path = ensure_path(PREFIX, url=url, name="picklist-api.json", force=force)
    with open(path) as f:
        data = json.load(f)
    terms = [
        CHARLIE_TERM,
        HUMAN_TERM,
        ROOT_TERM,
    ]
    for x in data:
        pp = ensure_path(PREFIX, "picklist", url=x["download_url"], backend="requests")
        with open(pp) as f:
            header, *rest = f.read().splitlines()
            name = header.removeprefix("# Contributor Roles/")
            dd = {k.removeprefix("## "): v for k, v in chunked(rest, 2)}
            identifier = (
                dd["Canonical URL"]
                .removeprefix("https://credit.niso.org/contributor-roles/")
                .rstrip("/")
            )
            desc = dd["Short definition"]
            terms.append(
                Term.from_triple(
                    prefix=PREFIX, identifier=identifier, name=name, definition=desc
                ).append_parent(ROOT)
            )

    return terms


if __name__ == "__main__":
    CreditGetter.cli()
