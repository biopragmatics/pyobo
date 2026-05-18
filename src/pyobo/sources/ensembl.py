"""Download ensembl."""

from collections.abc import Iterable
from pathlib import Path
from typing import Any

import requests
from pystow.utils import get_soup
from tqdm import tqdm

from pyobo import Reference, Term
from pyobo.struct.typedef import transcribes_to, translates_to
from pyobo.utils.path import ensure_path

PREFIX = "ensembl"


def get_files(*, force: bool = False) -> dict[str, Path]:
    """Ensure all JSON files from Ensembl."""
    version_res = requests.get("https://ftp.ensembl.org/pub/VERSION", timeout=5)
    version_res.raise_for_status()
    version: str = version_res.text.strip()
    soup = get_soup("https://ftp.ensembl.org/pub/current/json/")
    rv = {}
    for row in tqdm(soup.find_all("tr")):
        cells = list(row.find_all("td"))
        if len(cells) < 2 or cells[1].text == "Parent Directory":
            continue
        if (anchor := cells[1].find("a")) and anchor.text:
            name = anchor.text.strip("/")
            url = f"https://ftp.ensembl.org/pub/current/json/{name}/{name}.json"
            rv[name] = ensure_path(PREFIX, url=url, version=version, force=force)
    return rv


def parse_object(obj: dict[str, Any]) -> Iterable[Term]:
    """Parse a genomic object."""
    term = Term(
        reference=Reference(prefix="ensembl", identifier=obj["id"]),
        definition=obj["description"],
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


def main() -> None:
    """Download it all."""
    get_files()


if __name__ == "__main__":
    main()
