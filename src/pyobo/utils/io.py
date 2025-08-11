"""I/O utilities."""

import collections.abc
import gzip
import logging
from collections import defaultdict
from collections.abc import Generator, Iterable, Mapping
from contextlib import contextmanager
from pathlib import Path
from typing import TypeVar, cast

import pandas as pd
import pystow.utils
from pystow.utils import safe_open_reader, safe_open_writer
from tqdm.auto import tqdm

__all__ = [
    "multidict",
    "multisetdict",
    "open_map_tsv",
    "open_multimap_tsv",
    "safe_open_writer",
    "write_iterable_tsv",
    "write_map_tsv",
    "write_multimap_tsv",
]

logger = logging.getLogger(__name__)

X = TypeVar("X")
Y = TypeVar("Y")


def open_map_tsv(
    path: str | Path, *, use_tqdm: bool = False, has_header: bool = True
) -> Mapping[str, str]:
    """Load a mapping TSV file into a dictionary."""
    rv = {}
    with pystow.utils.safe_open_reader(path) as reader:
        if has_header:
            next(reader)  # throw away header
        if use_tqdm:
            reader = tqdm(reader, desc=f"loading TSV from {path}")
        for row in reader:
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
    with _help_multimap_tsv(path=path, use_tqdm=use_tqdm, has_header=has_header) as file:
        return multidict(file)


@contextmanager
def _help_multimap_tsv(
    path: str | Path,
    *,
    use_tqdm: bool = False,
    has_header: bool = True,
) -> Generator[Iterable[tuple[str, str]], None, None]:
    with safe_open_reader(path) as reader:
        if has_header:
            try:
                next(reader)  # throw away header
            except gzip.BadGzipFile as e:
                raise ValueError(f"could not open file {path}") from e
        if use_tqdm:
            yield tqdm(reader, desc=f"loading TSV from {path}")
        else:
            yield cast(Iterable[tuple[str, str]], reader)


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
