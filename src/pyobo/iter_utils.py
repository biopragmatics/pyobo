# -*- coding: utf-8 -*-

"""Tools for iterating over things."""

import gzip
from typing import Iterable, List, Tuple, TypeVar

from more_itertools import peekable

from .io_utils import split_tab_pair

X = TypeVar('X')
Z = TypeVar('Z')
Y = TypeVar('Y')

__all__ = [
    'iterate_together',
    'iterate_gzips_together',
]


def iterate_gzips_together(a_path, b_path) -> Iterable[Tuple[str, str, List[str]]]:
    """Iterate over two gzipped files together."""
    with gzip.open(a_path, mode='rt', errors='ignore') as a, gzip.open(b_path, mode='rt') as b:
        a = (split_tab_pair(line) for line in a)
        b = (split_tab_pair(line) for line in b)
        yield from iterate_together(a, b)


def iterate_together(a: Iterable[Tuple[X, Y]], b: Iterable[Tuple[X, Z]]) -> Iterable[Tuple[X, Y, List[Z]]]:
    """Iterate over two sorted lists that have the same keys.

    The lists have to have the following invariants:

    - a is a one-to-one mapping.
    - b is a one-to-many mapping.
    - Both are indexed with the same numbers and in sorted order.
    - Each key in the index is present within both files
    """
    b = peekable(b)
    b_index, _ = b.peek()

    for a_index, a_value in a:
        zs = []
        while a_index == b_index:
            _, b_value = next(b)
            zs.append(b_value)
            b_index, _ = b.peek((_Done, _Done))
        yield a_index, a_value, zs


class _Done:
    pass
