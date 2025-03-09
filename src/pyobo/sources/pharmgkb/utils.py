"""Utilities for PharmGKB."""

from collections.abc import Iterable
from pathlib import Path
from typing import cast

import pandas as pd
from pystow.utils import read_zipfile_csv
from tqdm import tqdm

from pyobo import Reference
from pyobo.utils.path import ensure_path

__all__ = [
    "download_pharmgkb_tsv",
]

AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/39.0.2171.95 Safari/537.36"


def download_pharmgkb(prefix: str, url: str, *, force: bool) -> Path:
    """Download a file from PharmGKB, spoofing the user agent."""
    return ensure_path(
        prefix,
        url=url,
        backend="requests",
        download_kwargs={
            "headers": {
                # This is required otherwise we get booted
                "User-Agent": AGENT,
            },
        },
        force=force,
    )


def download_pharmgkb_tsv(prefix: str, url: str, inner: str, *, force: bool) -> pd.DataFrame:
    """Download PharmGKB data."""
    path = download_pharmgkb(prefix, url=url, force=force)
    df = read_zipfile_csv(path, inner_path=inner, dtype=str)
    return df


def split(row, key: str) -> Iterable[str]:
    """Split the data."""
    values = row.get(key)
    if pd.isna(values) or not values:
        return
    try:
        for value in values.split(","):
            yield value.strip()
    except AttributeError:
        pass


_MISSING_PREFIXES: set[str] = set()
REPLACES = {
    "URL:http://www.ncbi.nlm.nih.gov/omim/": "omim:",
    "Comparative Toxicogenomics Database:": "mesh:",
    "ModBase:": "uniprot:",
    "RefSeq DNA:": "refseq:",
    "RefSeq RNA:": "refseq:",
    "RefSeq Protein:": "refseq:",
    "UCSC Genome Browser:": "refseq:",
}


def parse_xrefs(term, row, key="Cross-references") -> Iterable[Reference]:
    """Parse the cross-references."""
    for xref_curie in split(row, key):
        # HOXD@ is a valid genatlas identifier, see http://genatlas.medecine.univ-paris5.fr/fiche.php?symbol=HOXD@
        # but this is broken, so skip them for now
        if xref_curie.endswith("@"):
            continue
        for k, v in REPLACES.items():
            if xref_curie.startswith(k):
                xref_curie = xref_curie.replace(k, v)
        try:
            xref = cast(Reference, Reference.from_curie(xref_curie))
        except ValueError:
            p, _, _ = xref_curie.partition(":")
            if p not in _MISSING_PREFIXES:
                tqdm.write(f"[{term.curie}] could not parse xref: {xref_curie}")
            _MISSING_PREFIXES.add(p)
        else:
            yield xref
