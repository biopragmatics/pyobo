"""Loading of the relations ontology names."""

import csv
import os
from collections.abc import Mapping
from functools import lru_cache

import requests

__all__ = [
    "load_ro",
]

HERE = os.path.abspath(os.path.dirname(__file__))
PATH = os.path.join(HERE, "ro.tsv")
URL = "http://purl.obolibrary.org/obo/ro.json"
PREFIX = "http://purl.obolibrary.org/obo/"


@lru_cache(maxsize=1)
def load_ro() -> Mapping[tuple[str, str], str]:
    """Load the relation ontology names."""
    if not os.path.exists(PATH):
        download()
    with open(PATH) as file:
        return {
            (prefix, identifier): name
            for prefix, identifier, name in csv.reader(file, delimiter="\t")
        }


def download():
    """Download the latest version of the Relation Ontology."""
    rows = []
    res_json = requests.get(URL).json()
    for node in res_json["graphs"][0]["nodes"]:
        identifier = node["id"]
        if not identifier.startswith(PREFIX):
            continue
        identifier = identifier[len(PREFIX) :]
        if all(not identifier.startswith(p) for p in ("RO", "BFO", "UPHENO")):
            continue
        prefix, identifier = identifier.split("_", 1)
        name = node.get("lbl")
        if name:
            rows.append((prefix.lower(), identifier, name))

    with open(PATH, "w") as file:
        writer = csv.writer(file, delimiter="\t")
        writer.writerows(sorted(rows))


if __name__ == "__main__":
    download()
