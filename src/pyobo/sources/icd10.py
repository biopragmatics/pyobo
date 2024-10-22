"""Convert ICD-10 to OBO.

Run with python -m pyobo.sources.icd10 -v
"""

import logging
from collections.abc import Iterable, Mapping
from typing import Any

import click
from more_click import verbose_option
from tqdm.auto import tqdm

from ..sources.icd_utils import (
    ICD10_TOP_LEVEL_URL,
    get_child_identifiers,
    get_icd,
    visiter,
)
from ..struct import Obo, Reference, Synonym, Term
from ..utils.path import prefix_directory_join

__all__ = [
    "ICD10Getter",
]

logger = logging.getLogger(__name__)

PREFIX = "icd10"
VERSION = "2016"


class ICD10Getter(Obo):
    """An ontology representation of ICD-10."""

    ontology = PREFIX
    dynamic_version = True

    def iter_terms(self, force: bool = False) -> Iterable[Term]:
        """Iterate over terms in the ontology."""
        return iter_terms()


def get_obo() -> Obo:
    """Get ICD-10 as OBO."""
    return ICD10Getter()


def iter_terms() -> Iterable[Term]:
    """Iterate over ICD-10 terms."""
    r = get_icd(ICD10_TOP_LEVEL_URL)
    res_json = r.json()

    directory = prefix_directory_join(PREFIX, version=VERSION)

    chapter_urls = res_json["child"]
    tqdm.write(f"there are {len(chapter_urls)} chapters")

    visited_identifiers: set[str] = set()
    for identifier in get_child_identifiers(ICD10_TOP_LEVEL_URL, res_json):
        yield from visiter(
            identifier,
            visited_identifiers,
            directory,
            endpoint=ICD10_TOP_LEVEL_URL,
            converter=_extract_icd10,
        )


def _extract_icd10(res_json: Mapping[str, Any]) -> Term:
    identifier = res_json["code"]
    name = res_json["title"]["@value"]
    synonyms = [Synonym(synonym["label"]["@value"]) for synonym in res_json.get("synonym", [])]
    parents = [
        Reference(prefix=PREFIX, identifier=url[len(ICD10_TOP_LEVEL_URL) :])
        for url in res_json["parent"]
        if url[len(ICD10_TOP_LEVEL_URL) :]
    ]
    rv = Term(
        reference=Reference(prefix=PREFIX, identifier=identifier, name=name),
        synonyms=synonyms,
        parents=parents,
    )

    rv.append_property("class_kind", res_json["classKind"])

    return rv


@click.command()
@verbose_option
def _main():
    get_obo().write_default(use_tqdm=True)


if __name__ == "__main__":
    _main()
