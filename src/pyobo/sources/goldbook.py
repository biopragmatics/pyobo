"""An ontology representation of IUPAC Gold Book."""

import json.decoder
from collections.abc import Iterable

import pystow.utils
import requests
from tqdm import tqdm

from pyobo.struct import Obo, Reference, Term
from pyobo.utils.path import ensure_path

PREFIX = "goldbook"
URL = "https://goldbook.iupac.org/terms/index/all/json/download"
TERM_URL_FORMAT = "https://goldbook.iupac.org/terms/view/{}/json"


class GoldBookGetter(Obo):
    """An ontology representation of IUPAC Gold Book."""

    ontology = PREFIX
    dynamic_version = True

    def iter_terms(self, force: bool = False) -> Iterable[Term]:
        """Iterate over terms in the ontology."""
        return _iter_terms()


def _iter_terms() -> Iterable[Term]:
    res = requests.get(URL, timeout=15).json()
    for identifier in tqdm(res["terms"]["list"], unit_scale=True):
        if term := _get_term(identifier):
            yield term


def _get_term(identifier: str) -> Term | None:
    url = TERM_URL_FORMAT.format(identifier)
    try:
        path = ensure_path(PREFIX, "terms", url=url, name=f"{identifier}.json")
    except pystow.utils.DownloadError:
        tqdm.write(f"[{PREFIX}:{identifier}] failed to download {url}")
        return None

    try:
        with path.open() as file:
            res = json.load(file)
    except json.decoder.JSONDecodeError:
        tqdm.write(f"[{PREFIX}:{identifier}] failed to parse data in {path}")
        return None

    record = res["term"]
    definitions = record["definitions"]
    if definitions:
        definition = _clean(definitions[0]["text"])
    else:
        definition = None

    term = Term(
        reference=Reference(
            prefix=PREFIX,
            identifier=identifier,
            name=record["title"].strip(),
        ),
        definition=definition,
    )

    if synonym := record.get("synonym"):
        if synonym.startswith("<"):
            if synonym.startswith("<em>synonym</em>:"):
                synonym = synonym.removeprefix("<em>synonym</em>:")
                term.append_synonym(_clean(synonym))
            elif synonym.startswith("<em>synonyms</em>:"):
                for s in synonym.removeprefix("<em>synonyms</em>:").strip().split(","):
                    term.append_synonym(_clean(s))
            else:
                tqdm.write(f"[{term.curie}] issue with synonym: {synonym}")

    return term


def _clean(s: str) -> str:
    return s.strip().replace("\\n", "\n")


if __name__ == "__main__":
    GoldBookGetter.cli()
