"""Converter for the Contributor Roles Taxonomy."""

from __future__ import annotations

from collections.abc import Iterable

from more_itertools import chunked

from pyobo.struct import Obo, Term
from pyobo.utils.path import ensure_json, ensure_open

DATA_URL = "https://api.github.com/repos/CASRAI-CRedIT/Dictionary/contents/Picklists/Contributor%20Roles"
PREFIX = "credit"
ROOT_TERM = Term.from_triple(prefix="cro", identifier="0000000")
URI_PREFIX = "https://credit.niso.org/contributor-roles/"


class CreditGetter(Obo):
    """An ontology representation of the Contributor Roles Taxonomy."""

    ontology = PREFIX
    static_version = "2022"
    root_terms = [ROOT_TERM.reference]

    def iter_terms(self, force: bool = False):
        """Iterate over terms in the ontology."""
        yield ROOT_TERM
        for records in ensure_json(PREFIX, url=DATA_URL, name="picklist-api.json", force=force):
            with ensure_open(PREFIX, "picklist", url=records["download_url"], backend="requests") as file:
                header, *rest = file.read().splitlines()
                data = {key.removeprefix("## "): value for key, value in chunked(rest, 2)}
                term = Term.from_triple(
                    prefix=PREFIX,
                    identifier=data["Canonical URL"].removeprefix(URI_PREFIX).rstrip("/"),
                    name=header.removeprefix("# Contributor Roles/"),
                    definition=data["Short definition"],
                ).append_parent(ROOT_TERM)
                yield term


if __name__ == "__main__":
    CreditGetter.cli()
