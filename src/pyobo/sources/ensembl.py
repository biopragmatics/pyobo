"""Download ensembl."""

from collections.abc import Iterable
from pathlib import Path
from typing import Any

import requests
from pystow.utils import get_soup, gzip_compress, safe_open_json
from tqdm import tqdm

from pyobo import Obo, Reference, Term
from pyobo.struct.typedef import transcribes_to, translates_to
from pyobo.utils.path import ensure_path, join_path

__all__ = ["EnsemblGetter"]

PREFIX = "ensembl"
VERSION_URL = "https://ftp.ensembl.org/pub/VERSION"


class EnsemblGetter(Obo):
    """An ontology representation of the Ensembl database."""

    ontology = bioversions_key = PREFIX

    def iter_terms(self, force: bool = False) -> Iterable[Term]:
        """Iterate over terms in the ontology."""
        return iter_terms(version=self._version_or_raise, force=force)


def iterate_files(*, force: bool = False, version: str | None = None) -> Iterable[tuple[str, Path]]:
    """Ensure all JSON files from Ensembl."""
    if version is None:
        version = _get_latest_version()
        listing_url = "https://ftp.ensembl.org/pub/current/json/"
        url_fmt = "https://ftp.ensembl.org/pub/current/json/{name}/{name}.json"
    else:
        listing_url = f"https://ftp.ensembl.org/pub/release-{version}/json/"
        url_fmt = "https://ftp.ensembl.org/pub/release-{version}/json/{name}/{name}.json"

    soup = get_soup(listing_url)
    for row in tqdm(soup.find_all("tr"), desc="Processing Ensembl", unit="organism"):
        cells = list(row.find_all("td"))
        if len(cells) < 2 or cells[1].text == "Parent Directory":
            continue
        if (anchor := cells[1].find("a")) and anchor.text:
            name = anchor.text.strip("/")
            url = url_fmt.format(name=name, version=version)
            path = join_path(PREFIX, version=version, name=f"{name}.json.gz")
            if path.is_file() and not force:
                yield name, path
            else:
                unzipped_path = ensure_path(PREFIX, url=url, version=version, force=force)
                path = gzip_compress(unzipped_path, target=path, cleanup=True)
                yield name, path


def _get_latest_version() -> str:
    version_res = requests.get(VERSION_URL, timeout=5)
    version_res.raise_for_status()
    version: str = version_res.text.strip()
    return version


def parse_object(obj: dict[str, Any]) -> Iterable[Term]:
    """Parse a genomic object."""
    term = Term(
        reference=Reference(prefix="ensembl", identifier=obj["id"]),
        definition=obj.get("description"),
    )
    term.set_species(str(obj["taxon_id"]))
    for transcript in obj["transcripts"]:
        transcript_term = Term(
            reference=Reference(prefix="ensembl", identifier=transcript["id"]),
        )
        term.append_relationship(transcribes_to, transcript_term)
        for exon in transcript["exons"]:
            exon_term = Term(
                reference=Reference(prefix="ensembl", identifier=exon["id"]),
            )
            transcript_term.append_relationship(translates_to, exon_term)
            yield exon_term
        yield transcript_term
    yield term


def iter_terms(version: str | None = None, force: bool = False) -> Iterable[Term]:
    """Iterate over all Ensembl terms."""
    for name, path in iterate_files(version=version, force=force):
        data = safe_open_json(path)
        for obj in tqdm(data["genes"], desc=f"Processing {name}", unit="gene", unit_scale=True):
            yield from parse_object(obj)
