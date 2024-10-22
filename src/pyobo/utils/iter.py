"""Tools for iterating over things."""

import csv
import gzip
from collections.abc import Iterable
from typing import TypeVar

from more_itertools import peekable

__all__ = [
    "iterate_together",
    "iterate_gzips_together",
]

X = TypeVar("X")
Z = TypeVar("Z")
Y = TypeVar("Y")


def iterate_gzips_together(a_path, b_path) -> Iterable[tuple[str, str, list[str]]]:
    """Iterate over two gzipped files together."""
    with gzip.open(a_path, mode="rt", errors="ignore") as a, gzip.open(b_path, mode="rt") as b:
        a = csv.reader(a, delimiter="\t", quoting=csv.QUOTE_MINIMAL)
        b = csv.reader(b, delimiter="\t", quoting=csv.QUOTE_MINIMAL)
        yield from iterate_together(a, b)


def iterate_together(
    a: Iterable[tuple[X, Y]], b: Iterable[tuple[X, Z]]
) -> Iterable[tuple[X, Y, list[Z]]]:
    """Iterate over two sorted lists that have the same keys.

    The lists have to have the following invariants:

    - a is a one-to-one mapping.
    - b is a one-to-many mapping.
    - Both are indexed with the same numbers and in sorted order.
    - Each key in the index is present within both files
    """
    b_peekable = peekable(b)
    b_index, _ = b_peekable.peek()

    for a_index, a_value in a:
        zs = []
        while a_index == b_index:
            _, b_value = next(b_peekable)
            zs.append(b_value)
            b_index, _ = b_peekable.peek((_Done, _Done))
        yield a_index, a_value, zs


class _Done:
    pass
