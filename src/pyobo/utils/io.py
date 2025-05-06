"""I/O utilities."""

import collections.abc
import contextlib
import csv
import gzip
import logging
from collections import defaultdict
from collections.abc import Generator, Iterable, Mapping
from contextlib import contextmanager
from pathlib import Path
from typing import Literal, TextIO, TypeVar

import pandas as pd
from tqdm.auto import tqdm

__all__ = [
    "get_reader",
    "multidict",
    "multisetdict",
    "open_map_tsv",
    "open_multimap_tsv",
    "open_reader",
    "safe_open",
    "safe_open_writer",
    "write_iterable_tsv",
    "write_map_tsv",
    "write_multimap_tsv",
]

logger = logging.getLogger(__name__)

X = TypeVar("X")
Y = TypeVar("Y")


@contextmanager
def open_reader(path: str | Path, sep: str = "\t"):
    """Open a file and get a reader for it."""
    path = Path(path)
    with safe_open(path, read=True) as file:
        yield get_reader(file, sep=sep)


def get_reader(x, sep: str = "\t"):
    """Get a :func:`csv.reader` with PyOBO default settings."""
    return csv.reader(x, delimiter=sep, quoting=csv.QUOTE_MINIMAL)


def open_map_tsv(
    path: str | Path, *, use_tqdm: bool = False, has_header: bool = True
) -> Mapping[str, str]:
    """Load a mapping TSV file into a dictionary."""
    with safe_open(path, read=True) as file:
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
    path: str | Path,
    *,
    use_tqdm: bool = False,
    has_header: bool = True,
) -> Mapping[str, list[str]]:
    """Load a mapping TSV file that has multiple mappings for each."""
    return multidict(_help_multimap_tsv(path=path, use_tqdm=use_tqdm, has_header=has_header))


def _help_multimap_tsv(
    path: str | Path,
    *,
    use_tqdm: bool = False,
    has_header: bool = True,
) -> Iterable[tuple[str, str]]:
    with safe_open(path, read=True) as file:
        if has_header:
            try:
                next(file)  # throw away header
            except gzip.BadGzipFile as e:
                raise ValueError(f"could not open file {path}") from e
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
    path: str | Path,
    header: Iterable[str] | None = None,
    rv: Iterable[tuple[str, str]] | Mapping[str, str],
    sep: str = "\t",
) -> None:
    """Write a mapping dictionary to a TSV file."""
    if isinstance(rv, collections.abc.Mapping):
        write_iterable_tsv(path=path, header=header, it=rv.items(), sep=sep)
    else:
        write_iterable_tsv(path=path, header=header, it=rv, sep=sep)


def write_multimap_tsv(
    *,
    path: str | Path,
    header: Iterable[str],
    rv: Mapping[str, list[str]],
    sep: str = "\t",
) -> None:
    """Write a multiple mapping dictionary to a TSV file."""
    it = ((key, value) for key, values in rv.items() for value in values)
    write_iterable_tsv(path=path, header=header, it=it, sep=sep)


def write_iterable_tsv(
    *,
    path: str | Path,
    header: Iterable[str] | None = None,
    it: Iterable[tuple[str, ...]],
    sep: str = "\t",
) -> None:
    """Write a mapping dictionary to a TSV file."""
    it = (row for row in it if all(cell is not None for cell in row))
    it = sorted(it)
    with safe_open_writer(path, delimiter=sep) as writer:
        if header is not None:
            writer.writerow(header)
        writer.writerows(it)


@contextlib.contextmanager
def safe_open(
    path: str | Path, read: bool, encoding: str | None = None
) -> Generator[TextIO, None, None]:
    """Safely open a file for reading or writing text."""
    path = Path(path).expanduser().resolve()
    mode: Literal["rt", "wt"] = "rt" if read else "wt"
    if path.suffix.endswith(".gz"):
        with gzip.open(path, mode=mode, encoding=encoding) as file:
            yield file
    else:
        with open(path, mode=mode) as file:
            yield file


@contextlib.contextmanager
def safe_open_writer(f: str | Path | TextIO, *, delimiter: str = "\t"):  # type:ignore
    """Open a CSV writer, wrapping :func:`csv.writer`."""
    if isinstance(f, str | Path):
        with safe_open(f, read=False) as file:
            yield csv.writer(file, delimiter=delimiter)
    else:
        yield csv.writer(f, delimiter=delimiter)
