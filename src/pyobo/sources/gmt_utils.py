"""GMT utilities."""

from collections.abc import Iterable
from pathlib import Path

GMTSummary = tuple[str, str, set[str]]
WikiPathwaysGMTSummary = tuple[str, str, str, str, str, set[str]]


def parse_gmt_file(path: str | Path) -> Iterable[GMTSummary]:
    """Return file as list of pathway - gene sets (ENTREZ-identifiers).

    :param path: path to GMT file

    :yields: processed lines
    """
    with open(path) as file:
        for line in file:
            yield _process_line(line)


def _process_line(line: str) -> tuple[str, str, set[str]]:
    """Return the pathway name, url, and gene sets associated.

    :param line: gmt file line

    :returns: pathway name, pathway info url, and genes set associated
    """
    name, info, *entries = (p.strip() for p in line.split("\t"))
    return name, info, set(entries)


def parse_wikipathways_gmt(path: str | Path) -> Iterable[WikiPathwaysGMTSummary]:
    """Parse WikiPathways GMT."""
    for info, _uri, entries in parse_gmt_file(path):
        info, version, identifier, species = info.split("%")
        version = version.split("_")[1]  # removes the WikiPathways_
        # Revision isn't given anymore in GMT files
        # revision = uri.rsplit("_", 1)[1].lstrip("r")
        revision = ""
        yield identifier, version, revision, info, species, entries
