"""I/O utilities."""

import collections.abc
import csv
import gzip
import logging
import time
from collections import defaultdict
from collections.abc import Iterable, Mapping
from contextlib import contextmanager
from pathlib import Path
from typing import Optional, TypeVar, Union
from xml.etree.ElementTree import Element

import pandas as pd
from lxml import etree
from tqdm.auto import tqdm

__all__ = [
    "open_map_tsv",
    "open_multimap_tsv",
    "multidict",
    "multisetdict",
    "write_map_tsv",
    "write_multimap_tsv",
    "write_iterable_tsv",
    "parse_xml_gz",
    "get_writer",
    "open_reader",
    "get_reader",
]

logger = logging.getLogger(__name__)

X = TypeVar("X")
Y = TypeVar("Y")


@contextmanager
def open_reader(path: Union[str, Path], sep: str = "\t"):
    """Open a file and get a reader for it."""
    path = Path(path)
    with gzip.open(path, "rt") if path.suffix == ".gz" else open(path) as file:
        yield get_reader(file, sep=sep)


def get_reader(x, sep: str = "\t"):
    """Get a :func:`csv.reader` with PyOBO default settings."""
    return csv.reader(x, delimiter=sep, quoting=csv.QUOTE_MINIMAL)


def get_writer(x, sep: str = "\t"):
    """Get a :func:`csv.writer` with PyOBO default settings."""
    return csv.writer(x, delimiter=sep, quoting=csv.QUOTE_MINIMAL)


def open_map_tsv(
    path: Union[str, Path], *, use_tqdm: bool = False, has_header: bool = True
) -> Mapping[str, str]:
    """Load a mapping TSV file into a dictionary."""
    with open(path) as file:
        if has_header:
            next(file)  # throw away header
        if use_tqdm:
            file = tqdm(file, desc=f"loading TSV from {path}")
        rv = {}
        for row in get_reader(file):
            if len(row) != 2:
                logger.warning("[%s] malformed row can not be put in dict: %s", path, row)
                continue
            rv[row[0]] = row[1]
        return rv


def open_multimap_tsv(
    path: Union[str, Path],
    *,
    use_tqdm: bool = False,
    has_header: bool = True,
) -> Mapping[str, list[str]]:
    """Load a mapping TSV file that has multiple mappings for each."""
    return multidict(_help_multimap_tsv(path=path, use_tqdm=use_tqdm, has_header=has_header))


def _help_multimap_tsv(
    path: Union[str, Path],
    *,
    use_tqdm: bool = False,
    has_header: bool = True,
) -> Iterable[tuple[str, str]]:
    with open(path) as file:
        if has_header:
            next(file)  # throw away header
        if use_tqdm:
            file = tqdm(file, desc=f"loading TSV from {path}")
        yield from get_reader(file)


def multidict(pairs: Iterable[tuple[X, Y]]) -> Mapping[X, list[Y]]:
    """Accumulate a multidict from a list of pairs."""
    rv = defaultdict(list)
    for key, value in pairs:
        rv[key].append(value)
    return dict(rv)


def multisetdict(pairs: Iterable[tuple[X, Y]]) -> dict[X, set[Y]]:
    """Accumulate a multisetdict from a list of pairs."""
    rv = defaultdict(set)
    for key, value in pairs:
        if pd.notna(value):
            rv[key].add(value)
    return dict(rv)


def write_map_tsv(
    *,
    path: Union[str, Path],
    header: Optional[Iterable[str]] = None,
    rv: Union[Iterable[tuple[str, str]], Mapping[str, str]],
    sep: str = "\t",
) -> None:
    """Write a mapping dictionary to a TSV file."""
    if isinstance(rv, collections.abc.Mapping):
        write_iterable_tsv(path=path, header=header, it=rv.items(), sep=sep)
    else:
        write_iterable_tsv(path=path, header=header, it=rv, sep=sep)


def write_multimap_tsv(
    *,
    path: Union[str, Path],
    header: Iterable[str],
    rv: Mapping[str, list[str]],
    sep: str = "\t",
) -> None:
    """Write a multiple mapping dictionary to a TSV file."""
    it = ((key, value) for key, values in rv.items() for value in values)
    write_iterable_tsv(path=path, header=header, it=it, sep=sep)


def write_iterable_tsv(
    *,
    path: Union[str, Path],
    header: Optional[Iterable[str]] = None,
    it: Iterable[tuple[str, ...]],
    sep: str = "\t",
) -> None:
    """Write a mapping dictionary to a TSV file."""
    it = (row for row in it if all(cell is not None for cell in row))
    it = sorted(it)
    with open(path, "w") as file:
        writer = get_writer(file, sep=sep)
        if header is not None:
            writer.writerow(header)
        writer.writerows(it)


def parse_xml_gz(path: Union[str, Path]) -> Element:
    """Parse an XML file from a path to a GZIP file."""
    path = Path(path).resolve()
    t = time.time()
    logger.info("parsing xml from %s", path)
    tree = etree.parse(path.as_posix())  # type:ignore
    logger.info("parsed xml in %.2f seconds", time.time() - t)
    return tree.getroot()
