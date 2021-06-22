# -*- coding: utf-8 -*-

"""GMT utilities."""

from pathlib import Path
from typing import Iterable, Set, Tuple, Union

GMTSummary = Tuple[str, str, Set[str]]
WikiPathwaysGMTSummary = Tuple[str, str, str, str, str, Set[str]]


def parse_gmt_file(path: Union[str, Path]) -> Iterable[GMTSummary]:
    """Return file as list of pathway - gene sets (ENTREZ-identifiers).

    :param path: path to GMT file
    :return: line-based processed file
    """
    with open(path) as file:
        for line in file:
            yield _process_line(line)


def _process_line(line: str) -> Tuple[str, str, Set[str]]:
    """Return the pathway name, url, and gene sets associated.

    :param line: gmt file line
    :return: pathway name
    :return: pathway info url
    :return: genes set associated
    """
    name, info, *entries = (p.strip() for p in line.split("\t"))
    return name, info, set(entries)


def parse_wikipathways_gmt(path: Union[str, Path]) -> Iterable[WikiPathwaysGMTSummary]:
    """Parse WikiPathways GMT."""
    for name, info, entries in parse_gmt_file(path):
        name, version, identifier, species = name.split("%")
        version = version.split("_")[1]
        revision = info.rsplit("_", 1)[1].lstrip("r")
        yield identifier, version, revision, name, species, entries
