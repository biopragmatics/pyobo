"""An ontology representation of IUPAC Gold Book."""

import json.decoder
from collections.abc import Iterable
from typing import Any

import pystow.utils
import requests
from tqdm import tqdm

from pyobo.struct import Obo, Reference, Term
from pyobo.utils.path import ensure_json

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
    for luid, record in tqdm(res["terms"]["list"].items(), unit_scale=True):
        if term := _get_term(luid, record):
            yield term


def _get_term(luid: str, record: dict[str, Any]) -> Term | None:
    url = TERM_URL_FORMAT.format(luid)
    try:
        res = ensure_json(PREFIX, "terms", url=url, name=f"{luid}.json")
    except (json.decoder.JSONDecodeError, pystow.utils.DownloadError):
        tqdm.write(f"[{PREFIX}:{luid}] failed to parse data, see {url}")
        return None

    term = res["term"]
    definitions = term["definitions"]
    if definitions:
        definition = definitions[0]["text"]
    else:
        definition = None

    return Term(
        reference=Reference(
            prefix=PREFIX,
            identifier=luid,
            name=record["title"],
        ),
        definition=definition,
    )


if __name__ == "__main__":
    GoldBookGetter.cli()
