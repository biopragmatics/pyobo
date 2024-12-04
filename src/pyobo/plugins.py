"""Tools for loading entry points."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from functools import lru_cache

from .struct import Obo

__all__ = [
    "has_nomenclature_plugin",
    "iter_nomenclature_plugins",
    "run_nomenclature_plugin",
]


@lru_cache
def _get_nomenclature_plugins() -> Mapping[str, Callable[[], Obo]]:
    from .sources import ontology_resolver

    return ontology_resolver.lookup_dict


def has_nomenclature_plugin(prefix: str) -> bool:
    """Check if there's a plugin for converting the prefix."""
    from .sources import ontology_resolver

    try:
        ontology_resolver.lookup(prefix)
    except (KeyError, ValueError, TypeError):
        return False
    else:
        return True


def run_nomenclature_plugin(prefix: str, version: str | None = None) -> Obo:
    """Get a converted PyOBO source."""
    from .sources import ontology_resolver

    return ontology_resolver.make(prefix, data_version=version)


def iter_nomenclature_plugins() -> Iterable[Obo]:
    """Get all modules in the PyOBO sources."""
    from .sources import ontology_resolver

    for _prefix, cls in sorted(ontology_resolver.lookup_dict.items()):
        yield cls()
