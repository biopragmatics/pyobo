"""Loading of the NCBI Taxonomy names."""

import csv
import gzip
from collections.abc import Mapping
from functools import lru_cache
from pathlib import Path
from typing import Optional, Union

import requests

__all__ = [
    "load_ncbitaxon",
    "get_ncbitaxon_id",
    "get_ncbitaxon_name",
]

HERE = Path(__file__).parent.resolve()
PATH = HERE.joinpath("ncbitaxon.tsv.gz")
URL = "http://purl.obolibrary.org/obo/ncbitaxon.json"
URI_PREFIX = "http://purl.obolibrary.org/obo/NCBITaxon_"


@lru_cache(maxsize=1)
def load_ncbitaxon() -> Mapping[str, str]:
    """Load the NCBI Taxonomy identifier to name map."""
    return ensure(url=URL, path=PATH, uri_prefix=URI_PREFIX)


@lru_cache(maxsize=1)
def load_ncbitaxon_reverse() -> Mapping[str, str]:
    """Load the NCBI Taxonomy name to identifier map."""
    return {name: identifier for identifier, name in load_ncbitaxon().items()}


def get_ncbitaxon_name(ncbitaxon_id: str) -> Optional[str]:
    """Get the name from the identifier."""
    return load_ncbitaxon().get(ncbitaxon_id)


def get_ncbitaxon_id(name: str) -> Optional[str]:
    """Get the identifier from the name."""
    return load_ncbitaxon_reverse().get(name)


def ensure(url: str, path: Union[str, Path], uri_prefix: str) -> Mapping[str, str]:
    """Download the latest version of the resource."""
    path = Path(path)
    if path.is_file():
        with gzip.open(path, mode="rt") as file:
            return dict(csv.reader(file, delimiter="\t"))

    res_json = requests.get(url).json()

    rows = []
    for node in res_json["graphs"][0]["nodes"]:
        identifier = node["id"]
        if not identifier.startswith(uri_prefix):
            continue
        identifier = identifier[len(uri_prefix) :]
        name = node.get("lbl")
        if name:
            rows.append((identifier, name))

    with gzip.open(path, "wt") as file:
        writer = csv.writer(file, delimiter="\t")
        writer.writerows(sorted(rows))

    return dict(rows)


if __name__ == "__main__":
    load_ncbitaxon()
