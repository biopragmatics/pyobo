"""Loading of the relations ontology names."""

from __future__ import annotations

import csv
import os
from functools import lru_cache

import requests

__all__ = [
    "get_so_name",
    "load_so",
]

HERE = os.path.abspath(os.path.dirname(__file__))
SO_PATH = os.path.join(HERE, "so.tsv")
SO_JSON_URL = "https://github.com/The-Sequence-Ontology/SO-Ontologies/raw/refs/heads/master/Ontology_Files/so-simple.json"
SO_URI_PREFIX = "http://purl.obolibrary.org/obo/SO_"


def get_so_name(so_id: str) -> str | None:
    """Get the name from the identifier."""
    return load_so().get(so_id)


@lru_cache(maxsize=1)
def load_so() -> dict[str, str]:
    """Load the Sequence Ontology names."""
    if not os.path.exists(SO_PATH):
        download_so()
    with open(SO_PATH) as file:
        return dict(csv.reader(file, delimiter="\t"))


def download_so():
    """Download the latest version of the Relation Ontology."""
    rows = []
    res_json = requests.get(SO_JSON_URL).json()
    for node in res_json["graphs"][0]["nodes"]:
        uri = node["id"]
        if not uri.startswith(SO_URI_PREFIX):
            continue
        identifier = uri.removeprefix(SO_URI_PREFIX)
        name = node.get("lbl")
        if name:
            rows.append((identifier, name))

    with open(SO_PATH, "w") as file:
        writer = csv.writer(file, delimiter="\t")
        writer.writerows(sorted(rows, key=lambda x: int(x[0])))


if __name__ == "__main__":
    download_so()
