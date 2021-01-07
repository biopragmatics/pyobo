# -*- coding: utf-8 -*-

"""Iterate over OBO and nomenclature xrefs."""

import functools
import logging
import os
from typing import Optional

from ..extract import get_xrefs_df
from ..getters import iter_helper_helper
from ..path_utils import get_prefix_directory

__all__ = [
    'iterate_obo_xrefs',
]

logger = logging.getLogger(__name__)


def iterate_obo_xrefs(
    *,
    force: bool = False,
    use_tqdm: bool = True,
    skip_below: Optional[str] = None,
    skip_pyobo: bool = False,
    strict: bool = True,
):
    """Iterate over OBO Xrefs.

    :param force: If true, don't use cached xrefs tables
    :param use_tqdm:
    :param skip_pyobo: If true, skip prefixes that have PyOBO-implemented nomenclatures
    """
    it = iter_helper_helper(
        functools.partial(get_xrefs_df, force=force),
        strict=strict,
        use_tqdm=use_tqdm,
        skip_below=skip_below,
        skip_pyobo=skip_pyobo,
    )
    for prefix, df in it:
        if df is None:
            logger.debug('[%s] could not get a dataframe', prefix)
            continue

        df['source'] = prefix
        yield df

        prefix_directory = get_prefix_directory(prefix)
        if not os.listdir(prefix_directory):
            os.rmdir(prefix_directory)
