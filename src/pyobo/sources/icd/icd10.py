"""Convert ICD-10 to OBO.

Run with ``python -m pyobo.sources.icd10 -v``.

.. note::

    If web requests are stalling, try deleting the ``~/.cachier`` directory.
"""

import logging
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

from tqdm.auto import tqdm

from .icd_utils import (
    ICD10_TOP_LEVEL_URL,
    get_child_identifiers,
    get_icd_10_top,
    visiter,
)
from ...struct import Obo, Reference, Synonym, Term, has_category
from ...utils.path import prefix_directory_join

__all__ = [
    "ICD10Getter",
]

logger = logging.getLogger(__name__)

PREFIX = "icd10"
VERSION = "2016"


class ICD10Getter(Obo):
    """An ontology representation of ICD-10."""

    ontology = PREFIX
    static_version = VERSION
    typedefs = [has_category]

    def iter_terms(self, force: bool = False) -> Iterable[Term]:
        """Iterate over terms in the ontology."""
        return iter_terms(self._version_or_raise)


def _get_chapters(version: str, path: Path):
    res_json = get_icd_10_top(version=version, path=path)
    chapter_urls = res_json["child"]
    tqdm.write(f"there are {len(chapter_urls)} chapters")
    identifiers = get_child_identifiers(ICD10_TOP_LEVEL_URL, res_json)
    return identifiers


def iter_terms(version: str) -> Iterable[Term]:
    """Iterate over ICD-10 terms."""
    directory = prefix_directory_join(PREFIX, version=version)
    identifiers = _get_chapters(version=version, path=directory.joinpath("top.json"))

    visited_identifiers: set[str] = set()
    with tqdm(desc=f"[{PREFIX}]") as pbar:
        for identifier in identifiers:
            for term in visiter(
                identifier,
                visited_identifiers,
                directory,
                endpoint=ICD10_TOP_LEVEL_URL,
                converter=_extract_icd10,
            ):
                pbar.update(1)
                yield term


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
    rv.annotate_string(has_category, res_json["classKind"])

    return rv


if __name__ == "__main__":
    ICD10Getter.cli()
