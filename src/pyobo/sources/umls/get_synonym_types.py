"""Utilities for UMLS synonyms."""

import re
from collections.abc import Mapping
from pathlib import Path

import requests
from bs4 import BeautifulSoup

from pyobo.struct import SynonymTypeDef, default_reference
from pyobo.utils.io import open_map_tsv, write_map_tsv

__all__ = ["get_umls_synonyms", "get_umls_typedefs"]

HERE = Path(__file__).parent.resolve()
SYNONYM_TYPE_PATH = HERE.joinpath("synonym_types.tsv")

ABBREVIATIONS_URL = "https://www.nlm.nih.gov/research/umls/knowledge_sources/metathesaurus/release/abbreviations.html"
SPACES = re.compile(r"\s+")


def get_umls_synonyms(*, refresh: bool = False) -> Mapping[str, str]:
    """Get all synonyms."""
    if SYNONYM_TYPE_PATH.is_file() and not refresh:
        return open_map_tsv(SYNONYM_TYPE_PATH)
    res = requests.get(ABBREVIATIONS_URL, timeout=5)
    soup = BeautifulSoup(res.text, features="html.parser")
    table = soup.find(id="mrdoc_TTY")
    if table is None:
        raise ValueError
    body = table.find("tbody")  # type:ignore[attr-defined]
    if body is None:
        raise ValueError
    rv = {}
    for row in body.find_all("tr"):
        left, right = row.find_all("td")
        rv[left.text.strip()] = SPACES.sub(" ", right.text.strip())
    write_map_tsv(path=SYNONYM_TYPE_PATH, rv=rv, header=["key", "name"])
    return rv


def get_umls_typedefs(*, refresh: bool = False) -> dict[str, SynonymTypeDef]:
    """Get all synonym type definitions."""
    umls_synonyms = get_umls_synonyms(refresh=refresh)
    return {
        identifier: SynonymTypeDef(reference=default_reference("umls", identifier, name=name))
        for identifier, name in umls_synonyms.items()
    }


if __name__ == "__main__":
    get_umls_typedefs(refresh=True)
