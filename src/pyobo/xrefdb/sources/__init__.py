"""Sources of xrefs not from OBO."""

import logging
from collections.abc import Iterable, Mapping
from functools import lru_cache
from typing import Callable, Optional

import pandas as pd
from class_resolver import FunctionResolver
from tqdm.auto import tqdm

__all__ = [
    "iter_xref_plugins",
    "has_xref_plugin",
    "run_xref_plugin",
    "iter_xref_plugins",
]

logger = logging.getLogger(__name__)

XrefGetter = Callable[[], pd.DataFrame]


@lru_cache
def _get_xref_plugins() -> Mapping[str, XrefGetter]:
    resolver: FunctionResolver[XrefGetter] = FunctionResolver.from_entrypoint("pyobo.xrefs")
    return resolver.lookup_dict


def has_xref_plugin(prefix: str) -> bool:
    """Check if there's a plugin for converting the prefix."""
    return prefix in _get_xref_plugins()


def run_xref_plugin(prefix: str) -> pd.DataFrame:
    """Get a converted PyOBO source."""
    rv = _get_xref_plugins()[prefix]()

    if isinstance(rv, pd.DataFrame):
        return rv

    logger.warning("can not load %s since it yields many dataframes", prefix)


def iter_xref_plugins(
    use_tqdm: bool = True, skip_below: Optional[str] = None
) -> Iterable[pd.DataFrame]:
    """Get all modules in the PyOBO sources."""
    it = tqdm(sorted(_get_xref_plugins().items()), desc="Mapping Plugins", disable=not use_tqdm)
    for prefix, get_df in it:
        if skip_below and prefix < skip_below:
            continue
        it.set_postfix({"prefix": prefix})
        rv = get_df()
        if isinstance(rv, pd.DataFrame):
            yield rv
        elif isinstance(rv, Iterable):
            yield from rv
        else:
            raise TypeError
