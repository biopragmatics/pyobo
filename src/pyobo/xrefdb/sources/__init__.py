# -*- coding: utf-8 -*-

"""Sources of xrefs not from OBO."""

import logging
from functools import lru_cache
from typing import Callable, Iterable, Mapping

import pandas as pd
from pkg_resources import iter_entry_points

__all__ = [
    'iter_xref_plugins',
    'has_xref_plugin',
    'run_xref_plugin',
    'iter_xref_plugins',
]

logger = logging.getLogger(__name__)


@lru_cache()
def _get_xref_plugins() -> Mapping[str, Callable[[], pd.DataFrame]]:
    return {
        entry.name: entry.load()
        for entry in iter_entry_points(group='pyobo.xrefs')
    }


def has_xref_plugin(prefix: str) -> bool:
    """Check if there's a plugin for converting the prefix."""
    return prefix in _get_xref_plugins()


def run_xref_plugin(prefix: str) -> pd.DataFrame:
    """Get a converted PyOBO source."""
    rv = _get_xref_plugins()[prefix]()

    if isinstance(rv, pd.DataFrame):
        return rv

    logger.warning('can not load %s since it yields many dataframes', prefix)


def iter_xref_plugins() -> Iterable[pd.DataFrame]:
    """Get all modules in the PyOBO sources."""
    for _prefix, get_df in sorted(_get_xref_plugins().items()):
        rv = get_df()
        if isinstance(rv, pd.DataFrame):
            yield rv
        elif isinstance(rv, Iterable):
            yield from rv
        else:
            raise TypeError
