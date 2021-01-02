# -*- coding: utf-8 -*-

"""I/O utilities."""

import gzip
import logging
import time
from collections import defaultdict
from pathlib import Path
from typing import Iterable, List, Mapping, Set, Tuple, TypeVar, Union
from xml.etree import ElementTree
from xml.etree.ElementTree import Element

from tqdm import tqdm

__all__ = [
    'split_tab_pair',
    'open_map_tsv',
    'open_multimap_tsv',
    'multidict',
    'multisetdict',
    'write_map_tsv',
    'write_multimap_tsv',
    'write_iterable_tsv',
    'parse_xml_gz',
]

logger = logging.getLogger(__name__)

X = TypeVar('X')
Y = TypeVar('Y')


def split_tab_pair(x: str) -> Tuple[str, str]:
    """Split a pair of elements by a tab."""
    a, b = x.strip().split('\t')
    return a, b


def open_map_tsv(path: Union[str, Path], *, use_tqdm: bool = False) -> Mapping[str, str]:
    """Load a mapping TSV file into a dictionary."""
    with open(path) as file:
        next(file)  # throw away header
        if use_tqdm:
            file = tqdm(file, desc=f'loading TSV from {path}')
        return dict(split_tab_pair(line) for line in file)


def open_multimap_tsv(path: Union[str, Path], *, use_tqdm: bool = False) -> Mapping[str, List[str]]:
    """Load a mapping TSV file that has multiple mappings for each."""
    rv = defaultdict(list)
    with open(path) as file:
        next(file)  # throw away header
        if use_tqdm:
            file = tqdm(file, desc=f'loading TSV from {path}')
        for line in file:
            try:
                key, value = split_tab_pair(line)
            except ValueError:
                logger.warning('bad line: %s', line.strip())
            rv[key].append(value)
    return dict(rv)


def multidict(pairs: Iterable[Tuple[X, Y]]) -> Mapping[X, List[Y]]:
    """Accumulate a multidict from a list of pairs."""
    rv = defaultdict(list)
    for key, value in pairs:
        rv[key].append(value)
    return dict(rv)


def multisetdict(pairs: Iterable[Tuple[X, Y]]) -> Mapping[X, Set[Y]]:
    """Accumulate a multisetdict from a list of pairs."""
    rv = defaultdict(set)
    for key, value in pairs:
        rv[key].add(value)
    return dict(rv)


def write_map_tsv(
    *,
    path: Union[str, Path],
    header: Iterable[str],
    rv: Mapping[str, str],
    sep: str = '\t',
) -> None:
    """Write a mapping dictionary to a TSV file."""
    write_iterable_tsv(path=path, header=header, it=rv.items(), sep=sep)


def write_multimap_tsv(
    *,
    path: Union[str, Path],
    header: Iterable[str],
    rv: Mapping[str, List[str]],
    sep: str = '\t',
) -> None:
    """Write a multiple mapping dictionary to a TSV file."""
    it = (
        (key, value)
        for key, values in rv.items()
        for value in values
    )
    write_iterable_tsv(path=path, header=header, it=it, sep=sep)


def write_iterable_tsv(
    *,
    path: Union[str, Path],
    header: Iterable[str],
    it: Iterable[Tuple[str, str]],
    sep: str = '\t',
) -> None:
    """Write a mapping dictionary to a TSV file."""
    with open(path, 'w') as file:
        print(*header, sep=sep, file=file)
        for key, value in sorted(it):
            print(key, value, sep=sep, file=file)


def parse_xml_gz(path: Union[str, Path]) -> Element:
    """Parse an XML file from a path to a GZIP file."""
    t = time.time()
    logger.info('parsing xml from %s', path)
    with gzip.open(path) as file:
        tree = ElementTree.parse(file)
    logger.info('parsed xml in %.2f seconds', time.time() - t)
    return tree.getroot()
