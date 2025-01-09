"""Convert ICD11 to OBO.

Run with python -m pyobo.sources.icd11 -v
"""

import json
import logging
import os
from collections.abc import Iterable, Mapping
from typing import Any

from tqdm.auto import tqdm

from ..sources.icd_utils import (
    ICD11_TOP_LEVEL_URL,
    get_child_identifiers,
    get_icd,
    get_icd_11_mms,
    visiter,
)
from ..struct import Obo, Reference, Synonym, Term
from ..utils.path import prefix_directory_join

__all__ = [
    "ICD11Getter",
]

logger = logging.getLogger(__name__)

PREFIX = "icd11"


class ICD11Getter(Obo):
    """An ontology representation of ICD-11."""

    ontology = PREFIX
    dynamic_version = True

    def iter_terms(self, force: bool = False) -> Iterable[Term]:
        """Iterate over terms in the ontology."""
        return iterate_icd11()


def iterate_icd11() -> Iterable[Term]:
    """Iterate over the terms in ICD11 and enrich them with MMS."""
    res = get_icd(ICD11_TOP_LEVEL_URL)
    res_json = res.json()
    version = res_json["releaseId"]
    mms_directory = prefix_directory_join(PREFIX, "mms", version=version)
    for term in iterate_icd11_helper(res_json, version):
        path = mms_directory.joinpath(term.identifier).with_suffix(".json")
        if path.exists():
            mms_data = json.loads(path.read_text())
        else:
            mms_data = get_icd_11_mms(term.identifier)
            path.write_text(json.dumps(mms_data))

        if code := mms_data.get("code"):
            # TODO decide on ICD code prefix, then append this as a mapping
            term.annotate_literal("icd_mms_code", code)

        yield term


def iterate_icd11_helper(res_json, version) -> Iterable[Term]:
    """Iterate over the terms in ICD11.

    The API doesn't seem to have a rate limit, but returns pretty slow.
    This means that it only gets results at at about 5 calls/second.
    Get ready to be patient - the API token expires every hour so there's
    a caching mechanism with :mod:`cachier` that gets a new one every hour.
    """
    directory = prefix_directory_join(PREFIX, "base", version=version)
    top_path = directory.joinpath("top.json")
    with top_path.open("w") as file:
        json.dump(res_json, file, indent=2)

    tqdm.write(f'There are {len(res_json["child"])} top level entities')

    visited_identifiers: set[str] = set()
    for identifier in get_child_identifiers(ICD11_TOP_LEVEL_URL, res_json):
        yield from visiter(
            identifier,
            visited_identifiers,
            directory,
            endpoint=ICD11_TOP_LEVEL_URL,
            converter=_extract_icd11,
        )


def _extract_icd11(res_json: Mapping[str, Any]) -> Term:
    identifier = res_json["@id"][len(ICD11_TOP_LEVEL_URL) :].lstrip("/")
    if "definition" in res_json:
        definition = res_json["definition"]["@value"]
        definition = definition.strip().replace("\r\n", " ")
        definition = definition.strip().replace("\\n", " ")
        definition = definition.strip().replace("\n", " ")
    else:
        definition = None
    name = res_json["title"]["@value"]
    synonyms = [Synonym(synonym["label"]["@value"]) for synonym in res_json.get("synonym", [])]
    parents = [
        Reference(prefix=PREFIX, identifier=url[len("http://id.who.int/icd/entity/") :])
        for url in res_json["parent"]
        if url[len("http://id.who.int/icd/entity/") :]
    ]
    return Term(
        reference=Reference(prefix=PREFIX, identifier=identifier, name=name),
        definition=definition,
        synonyms=synonyms,
        parents=parents,
    )


if __name__ == "__main__":
    ICD11Getter.cli()
