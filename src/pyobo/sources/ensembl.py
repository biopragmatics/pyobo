"""Download ensembl."""

from pathlib import Path

import requests
from pystow.utils import get_soup
from tqdm import tqdm

from pyobo.utils.path import ensure_path

PREFIX = "ensembl"


def get_files(*, force: bool = False) -> dict[str, Path]:
    """Ensure all JSON files from Ensembl"""
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


def main() -> None:
    """Download it all."""
    get_files()


if __name__ == "__main__":
    main()
