# -*- coding: utf-8 -*-

"""Iterate over OBO and nomenclature xrefs."""

import logging
import os
from typing import Iterable, Optional

import bioregistry
import click
from more_click import verbose_option
from tqdm import tqdm

from ..extract import get_xrefs_df
from ..getters import NoBuild
from ..identifier_utils import MissingPrefix
from ..path_utils import get_prefix_directory
from ..sources import has_nomenclature_plugin

__all__ = [
    'iterate_obo_xrefs',
]

logger = logging.getLogger(__name__)

SKIP = {
    'obi',
    'ncbigene',  # too big, refs acquired from other dbs
    'pubchem.compound',  # to big, can't deal with this now
    'rnao',  # just really malformed, way too much unconverted OWL
    'gaz',
    'geo',
}
SKIP_XREFS = {
    'mamo', 'ido', 'iao', 'gaz', 'nbo', 'geo',
}


def iterate_obo_xrefs(
    *,
    force: bool = False,
    use_tqdm: bool = True,
    skip_below: Optional[str] = None,
    skip_pyobo: bool = False,
):
    """Iterate over OBO Xrefs.

    :param force: If true, don't use cached xrefs tables
    :param use_tqdm:
    :param skip_pyobo: If true, skip prefixes that have PyOBO-implemented nomenclatures
    """
    for prefix in iterate_bioregistry(use_tqdm=use_tqdm):
        if prefix in SKIP_XREFS:
            continue
        if skip_below and prefix < skip_below:
            continue
        if skip_pyobo and has_nomenclature_plugin(prefix):
            continue

        try:
            # FIXME encase this logic in pyobo.get
            df = get_xrefs_df(prefix, force=force)
        except MissingPrefix as e:
            e.ontology = prefix
            raise e
        except NoBuild:
            continue
        except ValueError as e:
            if (
                str(e).startswith('Tag-value pair parsing failed for:\n<?xml version="1.0"?>')
                or str(e).startswith('Tag-value pair parsing failed for:\n<?xml version="1.0" encoding="UTF-8"?>')
            ):
                logger.info('[%s] no resource available for %s', prefix, prefix)
                continue  # this means that it tried doing parsing on an xml page saying get the fuck out
            logger.warning('[%s] could not successfully parse: %s', prefix, e)
            continue

        if df is None:
            logger.debug('[%s] could not get a dataframe', prefix)
            continue

        df['source'] = prefix
        yield df

        prefix_directory = get_prefix_directory(prefix)
        if not os.listdir(prefix_directory):
            os.rmdir(prefix_directory)


def iterate_bioregistry(use_tqdm: bool = True) -> Iterable[str]:
    """Iterate over prefixes from the bioregistry."""
    it = sorted(bioregistry.read_bioregistry())
    if use_tqdm:
        it = tqdm(it, desc='Entries')
    for prefix in it:
        if bioregistry.is_deprecated(prefix) or prefix in SKIP:
            continue
        if use_tqdm:
            it.set_postfix({'prefix': prefix})
        yield prefix


@click.command()
@verbose_option
def _main():
    for _ in iterate_obo_xrefs(force=True, skip_pyobo=True):
        pass


if __name__ == '__main__':
    _main()
