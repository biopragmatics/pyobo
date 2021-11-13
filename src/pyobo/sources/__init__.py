# -*- coding: utf-8 -*-

"""Sources of OBO content."""

from functools import lru_cache
from typing import Callable, Iterable, Mapping

from pkg_resources import iter_entry_points

from ..struct import Obo

__all__ = [
    "has_nomenclature_plugin",
    "run_nomenclature_plugin",
    "iter_nomenclature_plugins",
]


@lru_cache()
def _get_nomenclature_plugins() -> Mapping[str, Callable[[], Obo]]:
    return {entry.name: entry.load() for entry in iter_entry_points(group="pyobo.nomenclatures")}


def has_nomenclature_plugin(prefix: str) -> bool:
    """Check if there's a plugin for converting the prefix."""
    return prefix in _get_nomenclature_plugins()


def run_nomenclature_plugin(prefix: str) -> Obo:
    """Get a converted PyOBO source."""
    return _get_nomenclature_plugins()[prefix]()


def iter_nomenclature_plugins() -> Iterable[Obo]:
    """Get all modules in the PyOBO sources."""
    for _prefix, get_obo in sorted(_get_nomenclature_plugins().items()):
        yield get_obo()
